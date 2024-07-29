import json as j, base64, itertools as i, socket, struct
from typing import Callable, Dict, Tuple,List,Set,Union
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

def zbx_discover_packet(zabbix_host: str,jsons):
    function_names = [json['dimensions']['FunctionName'] for json in jsons]
    fn_tups = [
        (
            fn,
            res.get('Tags',{}),
            res.get('Configuration',{'FunctionArn':''}).get('FunctionArn','')
        )
        for fn in function_names # tuples of function name and its tags
        for res in list(__catch_default(lambda_client.get_function,{'Tags':{},'Configuration':{'FunctionArn':''}},FunctionName=fn))
                                                                    # non-existent functions and functions without tags will be ignored
    ]
    fn_tups = filter(lambda e: ZBX_MONITORED_TAG not in e[1], fn_tups) # only discover new functions
    
    untracked = filter(lambda e: AWS_PRIO_TAG not in e[1],fn_tups) # functions without the PRIO tag, non-existent functions and functions with no tags at all
    fn_tups = filter(lambda e: e[0] not in untracked, fn_tups) # keep only functions with PRIO tag
    fn_tups = list(fn_tups)

    for fn in fn_tups:
        lambda_client.tag_resource(
            Resource=fn[2],
            Tags={ZBX_MONITORED_TAG: "true"}
        )

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
                        for function_name,fn_tags in fn_tups
                    ])
                }
            ]
         }
    ).encode("utf-8") # encode to bytes object for socket
    return packet, untracked

def zbx_mass_item_packet(jsons,zbx_sender_data:Callable[[str,Dict,str],List[Dict]],ignore_names:Union[Set,None]=None):
    '''
    Creates a single monoliTHICC packet including all functions and metrics
    
    :param jsons: parsed json objects with extract_data
    :param zbx_sender_data: function that accepts name of metric, its values and function name and returns 
                            a list of dictionaries corresponding to the zabbix sender protocol data field
                            - each has 'host' (zabbix host), 'key' (key of the item) and 'value' (value to push to the item).
                            The function returns a list in case one AWS metric translates to more Zabbix metrics,
                            e.g. the Duration metric may translate to max.duration and min.duration in zabbix, 
                            thus the function returns two dictionaries
    :param untracked_functions: set of function names to ignore
    '''
    ignore_names = ignore_names or {}
    # get zabbix data objects for each metric and function, and update the objects with timestamps
    sender_data = [
                list(map(lambda e: {
                                **e,
                                'clock': {int(json['timestamp'])//1000},          # timestamp in miliseconds -- extract seconds
                                'ns': {(int(json['timestamp'])%1000)*1_000_000}  # exctract miliseconds and convert to nanoseconds
                            },
                         zbx_sender_data(json['metric_name'],json['value'],json['dimensions']['FunctionName'])
                    ))
                for json in jsons
                if json['dimensions']['FunctionName'] not in ignore_names]
    sender_data = list(i.chain(*sender_data))
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
    s=socket.create_connection(addr)
    s.sendall(b"ZBXD\1" + struct.pack("<II",len(data),0) + data)
    o = s.recv(1024)
    s.close()
    return o