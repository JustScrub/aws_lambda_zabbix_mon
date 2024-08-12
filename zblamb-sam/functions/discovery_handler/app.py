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
        (name, arn, tags)
        for page in lambda_client.get_paginator('list_functions').paginate()
        for name, arn in map(lambda fn: (fn['FunctionName'],fn['FunctionArn']), page['Functions'])
        for tags in [lambda_client.get_function(FunctionName=name).get('Tags',{})]
    ] # tuples of function name, ARN and Tags field

    functions = list(filter(
        lambda e: AWS_PRIO_TAG in e[2],
        functions
    )) # only discover functions with the AWS_PRIO_TAG tag -- the rest are untracked by Zabbix

    # tag the discovered functions
    for name,arn,tags in functions:
        if AWS_DISCOVERED_TAG in tags: continue # only add tag to new functions, not yet discovered
        lambda_client.tag_resource(
            Resource=arn,
            Tags={AWS_DISCOVERED_TAG: "true"} 
        )
    
    packet = [
                {
                    f"{{#{ZBX_FN_NAME_MACRO}}}": name,
                    f"{{#{ZBX_PRIO_MACRO}}}": f"{tags[AWS_PRIO_TAG]}"
                }
                for name,arn,tags in functions
            ]
    return packet

def lambda_handler(e,c):
    discovery_value = zbx_discover_all()
    discovery_str = j.dumps(discovery_value)
    logger.info("Discovered functions: %s", discovery_str)
    sender = Sender(os.environ['ZBLAMB_PROXY_IP'],10051)
    sender.set_timeout(0.5)
    resp = sender.send_value(ZBX_SUFFIX,f"discover.{ZBX_SUFFIX}",discovery_str)
    logger.info("Response: %s",str(resp))

    err = resp.response != 'success'
    if resp.failed > 0:
        logger.error(f"Zabbix discovery failed for {resp.failed} functions!")
        err = True
    if resp.total == 0 and len(discovery_value) > 0:
        logger.fatal(f"No functions discovered! Is the Zabbix sender packet correct?")
        err = True

    logger.info(f"Zabbix took {resp.seconds_spent} seconds on the request.")

    if err:
        exit(1)
    else:
        return {"status": "ok", "discovered": len(discovery_value)}

