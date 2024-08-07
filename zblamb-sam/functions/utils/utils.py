import json as j, base64, itertools as i, socket, struct
from typing import Dict,Tuple,Set,Union
import boto3
import time
from config import *

lambda_client = boto3.client("lambda")

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

def __catch_default(func,default,*args,**kwargs):
    try:
        return func(*args,**kwargs)
    except:
        return default

def __should_discover(fn_tup):
    t = int(fn_tup[1].get(ZBX_MONITORED_TAG,0)) # get expiry timestamp or the value 0, if timestamp tag does not exist
    return t < time.time_ns()                   # time.time_ns() is always greater than zero

def zbx_discover_packet(zabbix_host: str,jsons):
    function_names = [json['dimensions']['FunctionName'] for json in jsons]
    fn_tups = [
        (
            fn,
            res.get('Tags',{}),
            res.get('Configuration',{'FunctionArn':''}).get('FunctionArn','')
        )
        for fn in function_names # tuples of function name and its tags
        for res in [__catch_default(lambda_client.get_function,{'Tags':{},'Configuration':{'FunctionArn':''}},FunctionName=fn)]
                                                                    # non-existent functions and functions without tags will be ignored
    ]
    
    untracked = set(
            map(lambda e: e[0], 
                filter(lambda e: AWS_PRIO_TAG not in e[1],fn_tups)
                )
            ) # names of functions without the PRIO tag, non-existent functions and functions with no tags at all
    fn_tups = filter(lambda e: e[0] not in untracked, fn_tups) # keep only functions with PRIO tag
    fn_tups = filter(__should_discover, fn_tups) # only discover new and possibly expired functions
    fn_tups = list(fn_tups)

    # if len(fn_tups) == 0: return None,untracked

    for fn in fn_tups:
        lambda_client.tag_resource(
            Resource=fn[2],
            Tags={ZBX_MONITORED_TAG: f"{time.time_ns() + int(ZBX_LLD_KEEP_PERIOD)*500_000_000}"} # convert half of the ZBX_LLD_KEEP_PERIOD to nanoseconds (P=2 => 63.21 % chance of re-discovery of least frequent, see README.md)
        )
        # NOTE: The tag will not be updated and function will not be discovered with each metric update.
        #       The Lambda function will be re-discovered in half of the period
        #       If ZBX_LLD_KEEP_PERIOD is set to the expected invocation period of the least frequent function,
        #       the probability of falsely deleting it in Zabbix is ~ 37 %.
        #       Probability of more frequent functions getting falsely deleted is lower -- the higher the frequency, the lower the probability

        # NOTE: The timestamp tag should be updated BEFORE sending discovery to Zabbix (as it currently is).
        #       The tag will contain current time, but the discovery packet will arrive at a later time.
        #       This means re-discovery has slightly more time and the probability of false deletion in Zabbix is lowered.
        #       If it were the other way, tag timestamp would be later than actual expiry time in Zabbix
        #       and discovery might not be sent to already dropped items, so the metrics would be lost, 
        #       since Zabbix no longer knows the items.

    discovery_item = f"discover.{zabbix_host}"
    packet = j.dumps(
         {
            "request":"sender data",  # zabbix_sender request to zabbix server -- only trapper items are used
            "data": 
            [
                {
                    "host": zabbix_host,
                    "key": discovery_item,
                    "value": j.dumps([
                        {
                            f"{{#{ZBX_FN_NAME_MACRO}}}": function_name,
                            f"{{#{ZBX_PRIO_MACRO}}}": f"{fn_tags[AWS_PRIO_TAG]}"
                        }
                        for function_name,fn_tags,_ in fn_tups
                    ])
                }
            ]
         }
    ).encode("utf-8") # encode to bytes object for socket
    return packet, untracked


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
    sender_data = [
        {
            "host": zabbix_host,
            "key": f"{item}.metrics.{zabbix_host}[{json['dimensions']['FunctionName']}]",
            "value": json['value'][stat],
            'clock': f"{int(json['timestamp'])//1000}",          # timestamp in miliseconds -- extract seconds
            'ns': f"{(int(json['timestamp'])%1000)*1_000_000}"  # exctract miliseconds and convert to nanoseconds
        }
        for json in jsons
        for metric in [metric_map[json['metric_name']]]
        for stat in metric
        for item in metric[stat]
        if json['dimensions']['FunctionName'] not in ignore_names
    ]
    ts = time.time_ns()


    return j.dumps(
        {
            "request":"sender data",  # zabbix_sender request to zabbix server -- only trapper items are used
            "data": sender_data,
            "clock": ts//1_000_000_000,  # extract seconds
            "ns": ts%1_000_000_000       # extract fractional nanoseconds
        }
    ).encode("utf-8") # encode to bytes object for socket

def zbx_send_packet(addr:Tuple[str,str],data: bytes):
    s=socket.create_connection(addr,timeout=1)
    s.sendall(b"ZBXD\1" + struct.pack("<II",len(data),0) + data)
    o = s.recv(1024)
    s.close()
    return o