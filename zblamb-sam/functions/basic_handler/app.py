
import json as j, base64, itertools as i, time, os, logging
from zappix.sender import Sender
from zappix.protocol import SenderData
from typing import Dict,Set,Union
from config import *
import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'WARNING').upper())

def extract_data(evt:Dict):
    firehose_data= evt['records'] # a list of firehose records
    firehose_data= [ base64.b64decode(r['data']).decode('utf-8') for r in firehose_data ] # only take the 'data' parameter of the record and decode it from base64
    firehose_data= i.chain(*[data.splitlines() for data in firehose_data]) # decoded data contains json files separated by newlines -- chain all json files into a flat list
    firehose_data= map(j.loads, firehose_data) # convert the string jsons to python dictionaries and lists
    firehose_data= filter( 
        lambda json: list(json['dimensions'].keys())==['FunctionName'],
        firehose_data  ) # only keep those jsons, where the 'dimensions' parameter object has only the 'FunctionName' parameter
    # one-liner: 
    # firehose_data= i.chain(*[ list(filter(lambda j: list(j['dimensions'].keys())==['FunctionName'],map( json.loads,base64.b64decode(r['data']).decode('utf-8').splitlines() )))  for r in e['records']])
    return list(firehose_data)

def ignore_fns(jsons):
    lc = boto3.client('lambda')
    ignores = {
        name
        for json in jsons
        for name in [json['dimensions']['FunctionName']]
        for tags in [lc.get_function(FunctionName=name).get('Tags',{})]
        if AWS_PRIO_TAG not in tags or AWS_DISCOVERED_TAG not in tags
    }
    lc.close()
    return ignores

def __load_metric_map():
    with open("metric_map.json", "r") as f:
        return j.load(f)

def zbx_mass_item_packet(jsons,zabbix_host,ignore_names:Union[Set,None]=None):
    '''
    Creates a single monoliTHICC packet including all functions and metrics
    
    :param jsons: parsed json objects with extract_data
    :param zabbix_host: name of the Zabbix host, from which item names are derived: <zbx_metric>.metrics.<zabbix_host>[<function_name>]
    :param ignore_names: set of function names to ignore
    '''
    ignore_names = ignore_names or {}
    metric_map = __load_metric_map()
    # get zabbix data objects for each metric and function, and update the objects with timestamps
    sender_data = [SenderData(
            **{
                "host": zabbix_host,
                "key": f"{item}.metrics.{zabbix_host}[{json['dimensions']['FunctionName']}]",
                "value": json['value'][stat],
                'clock': int(json['timestamp'])//1000,          # timestamp in miliseconds -- extract seconds
                'ns': (int(json['timestamp'])%1000)*1_000_000  # exctract miliseconds and convert to nanoseconds
            }
        )
        for json in jsons
        for metric in [metric_map[json['metric_name']]]  # list of single value, used as a helper variable lol
        for stat in metric
        for item in metric[stat]
        if json['dimensions']['FunctionName'] not in ignore_names
    ]
    return sender_data

def lambda_handler(e,c):
    logger.info("Event %s",e)
    zbx_addr = (os.environ['ZBLAMB_PROXY_IP'],10051)

    # extract metrics
    sender_data = extract_data(e)

    # send metrics to Zabbix
    ignored = ignore_fns(sender_data)
    logger.info("Ignoring functions: %s",ignored)

    sender_data = zbx_mass_item_packet(sender_data,ZBX_SUFFIX,ignored)
    logger.info("Item data: %s",sender_data)

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