
import json as j, base64, os, logging, re
from zappix.sender import Sender
from zappix.protocol import SenderData
from typing import Dict,Set,Union
from config import *
import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'WARNING').upper())

__function_names = set()

def __dimension_filter(str_json:str):
    m = re.search(
        r'"dimensions"\s*:\s*', # search for dimensions property
        str_json
    )
    if m is None:
        return False # no dimensions property, should not happen
    
    m = re.match(
        r'{\s*"FunctionName"\s*:\s*"([^"]+)"\s*}', # match if the dimensions object only has the FunctionName property
        str_json[m.end():]
    )
    if m is not None:
        __function_names.add(m.group(1))
        return True
    return False
    # I think it is faster to check this in-string, without converting everything to json and then filtering out

def extract_data(evt:Dict):
    firehose_data= evt['records'] # a list of firehose records
    firehose_data= [ base64.b64decode(r['data']).decode('utf-8') for r in firehose_data ] # only take the 'data' parameter of the record and decode it from base64
    flat = [] # decoded data contains json files separated by newlines -- chain all json files into a flat list
    for data in firehose_data: flat.extend(data.splitlines()) # apparently the fastest method of flattening: https://stackoverflow.com/questions/49631326/why-is-itertools-chain-faster-than-a-flattening-list-comprehension
    firehose_data= flat 
    firehose_data= filter( __dimension_filter, firehose_data  ) # only keep those jsons, where the 'dimensions' parameter object has only the 'FunctionName' parameter
    firehose_data= map(j.loads, firehose_data) # convert the remaining string jsons to python dictionaries and lists
    # one-liner: 
    # firehose_data= i.chain(*[ list(filter(lambda j: list(j['dimensions'].keys())==['FunctionName'],map( json.loads,base64.b64decode(r['data']).decode('utf-8').splitlines() )))  for r in e['records']])
    return list(firehose_data)

def ignore_fns():
    lc = boto3.client('lambda')
    ignores = {
        name
        for name in __function_names
        for tags in [lc.get_function(FunctionName=name).get('Tags',{})]
        if AWS_PRIO_TAG not in tags or AWS_DISCOVERED_TAG not in tags
    }
    lc.close()
    return ignores

def zbx_mass_item_packet(jsons,zabbix_host,ignore_names:Union[Set,None]):
    '''
    Creates a single monoliTHICC packet including all functions and metrics
    
    :param jsons: parsed json objects with extract_data
    :param zabbix_host: name of the Zabbix host, from which item names are derived: <zbx_metric>.metrics.<zabbix_host>[<function_name>]
    :param ignore_names: set of function names to ignore
    '''
    # get zabbix data objects for each metric and function, and update the objects with timestamps
    sender_data = [SenderData(
            host= zabbix_host,
            key= f"{stat.lower()}.{metric.lower()}.metrics.{zabbix_host}[{json['dimensions']['FunctionName']}]",
            value= json['value'][stat],
            clock= int(json['timestamp'])//1000,          # timestamp in miliseconds -- extract seconds
            ns= (int(json['timestamp'])%1000)*1_000_000  # exctract miliseconds and convert to nanoseconds
        )
        for json in jsons
        for metric in [json['metric_name']]  # list of single value, used as a helper variable lol
        for stat in AWS_METRIC_SELECT[metric]
        if json['dimensions']['FunctionName'] not in ignore_names
    ]
    return sender_data

def lambda_handler(e,c):
    logger.debug("Event %s",e)
    zbx_addr = (os.environ['ZBLAMB_PROXY_IP'],10051)

    # extract metrics
    sender_data = extract_data(e)

    # send metrics to Zabbix
    ignored = ignore_fns()
    logger.info("Ignoring functions: %s",ignored)

    sender_data = zbx_mass_item_packet(sender_data,ZBX_SUFFIX,ignored)
    logger.info("Number of data: %s", len(sender_data))
    logger.debug("Item data: %s",sender_data)

    sender = Sender(*zbx_addr)
    sender.set_timeout(0.5)
    resp = sender.send_bulk(sender_data,with_timestamps=True)
    logger.info("Item response: %s",resp)

    err = resp.response != "success"
    if resp.failed > 0:
        logger.error(f"Zabbix item processing failed for {resp.failed} metrics!")
        err = True
    if resp.total == 0 and len(sender_data) > 0:
        logger.fatal(f"No metrics delivered! Is the Zabbix sender packet correct?")
        err = True
    elif resp.total < len(sender_data):
        logger.error(f"Zabbix dropped {len(sender_data) - resp.total} metrics (nor processed, nor failed)!")
        err = True
    logger.info(f"Zabbix took {resp.seconds_spent} seconds on the request.")

    if err: exit(1)
    return {'records': [{'recordId': r['recordId'],'result': 'Dropped','data': ''} for r in e['records']]} # drop all data, do not send it further via firehose