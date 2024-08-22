import boto3, json as j
from zappix.sender import Sender
from config import *
import os, logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'WARNING').upper())
lambda_client = boto3.client("lambda")

def __catch_default(func,default,*args,**kwargs):       # use in case lambda_client.get_function is throwing exceptions:
    try:                                                # for tags in [__catch_exception(lambda_client.get_function,{'Tags':{}},FunctionName=name).get('Tags',{})]
        return func(*args,**kwargs)
    except:
        return default

def zbx_discover_all():
    functions =  [
        (name, vars)
        for page in lambda_client.get_paginator('list_functions').paginate()
        for name in map(lambda fn: fn['FunctionName'], page['Functions'])
        for vars in [__catch_default( # try to exctract environment variables -- in case of failure, return empty dictionary
                lambda fn: lambda_client.get_function(FunctionName=fn)['Configuration']['Environment']['Variables'],
                {},
                name
            )]
    ] # tuples of function name and Env vars field


    functions = list(filter(
        lambda e: AWS_PRIO_VAR in e[1],
        functions
    )) # only discover functions with the AWS_PRIO_VAR env var -- the rest are untracked by Zabbix

    for name,vars in functions:
        # parse the priority variable -- e.g. PRIO = "errors:1 max.duration:4 count_avg.duration:2"
        vars['parsed'] = {
            f"{{#{metric_name.upper()}_{ZBX_PRIO_MACRO}}}": f"{priority}"

            for prio_pair in vars[AWS_PRIO_VAR].split()
            for metric_name,priority in [prio_pair.split(':')]
        }
    
    packet = [
                {
                    f"{{#{ZBX_FN_NAME_MACRO}}}": name,
                    **(vars['parsed'])
                }
                for name,vars in functions
            ]
    return packet, [f[0] for f in functions]

def flag_functions(names_with_prio):
    # NOTE: somewhat critical section on all function's Environment Variables is entered
    #       if someone updates environment variables for of any function with the AWS_DISCOVERED_VAR not present,
    #       the changes may be reverted after the function is flagged
    for name in names_with_prio:
        vars = lambda_client.get_function(FunctionName=name)['Configuration']['Environment']['Variables'] #shouldn't fail as the input function names are required to have at least the prio var
        if AWS_DISCOVERED_VAR in vars: continue
        vars.update({AWS_DISCOVERED_VAR: "true"})
        lambda_client.update_function_configuration(
            FunctionName=name,
            Environment={
                "Variables": vars
            }
        )

def lambda_handler(e,c):
    discovery_value,discovered_names = zbx_discover_all()
    discovery_str = j.dumps(discovery_value)
    logger.info("Discovered functions: %s", discovery_str)

    if not discovery_value:
        logger.info(f"No functions to discover.")
        return {"status": "ok", "discovered": len(discovery_value)}


    sender = Sender(os.environ['ZBLAMB_PROXY_IP'],10051)
    sender.set_timeout(0.5)
    resp = sender.send_value(ZBX_SUFFIX,f"discover.{ZBX_SUFFIX}",discovery_str)
    logger.info("Response: %s",str(resp))

    err = resp.response != 'success'
    if resp.failed > 0:
        logger.error(f"Zabbix discovery failed!")
        err = True
    if resp.total == 0 and len(discovery_value) > 0:
        logger.fatal(f"No functions discovered! Is the Zabbix sender packet correct?")
        err = True

    logger.info(f"Zabbix took {resp.seconds_spent} seconds on the request.")

    if err:
        exit(1)
    else:
        flag_functions(discovered_names) # do not flag them if the discovery failed
        return {"status": "ok", "discovered": len(discovery_value)}

