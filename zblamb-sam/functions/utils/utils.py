import json as j, base64, itertools as i, socket, struct
from typing import Callable, Dict, Tuple
import boto3

##### CONFIG #######
PRIO_TAG="PRIO" # tag of lambda function assigning its priority
ZBX_PRIO_MACRO="PRIO" # LLD macro for Zabbix that will be evaluated to the function priority
ZBX_FN_NAME_MACRO="FN_NAME" # LLD macro for Zabbix that will be evaluated to the function name
##### END CONFIG #####

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

def zbx_discover(addr:Tuple[str,str],zabbix_discovery_host: str,jsons):
    function_names = [json['dimensions']['FunctionName'] for json in jsons]
    tags = [(fn,lambda_client.get_function(FunctionName=fn)['Tags']) for fn in function_names] # function and its tags tuples
    untracked = set(filter(lambda e: PRIO_TAG not in e[1],tags)) # functions without the PRIO tag
    tags = filter(lambda e: e[0] not in untracked, tags) # keep only functions with PRIO tag

    discovery_item = f"discover.{zabbix_discovery_host}"
    packet = j.dumps(
         {
            "request":"sender data",  # zabbix_sender request to zabbix server -- only trapper items are used
            "data": 
            [
                {
                    "host": zabbix_discovery_host,
                    "key": discovery_item,
                    "data": j.dumps([
                        {
                            f"{{#{ZBX_FN_NAME_MACRO}}}": function_name,
                            f"{{#{ZBX_PRIO_MACRO}}}": f"{fn_tags[PRIO_TAG]}"
                        }
                        for function_name,fn_tags in tags
                    ])
                }
            ]
         }
    ).encode("utf-8") # encode to bytes object for socket
    return zbx_send_packet(addr,packet), untracked

def zbx_item_packet(jsons,zbx_sender_data):
    '''
    :param jsons: parsed json objects with extract_data
    :param zbx_sender_data: function that accepts name of metric, its values and function name and returns 
                            a list of dictionaries corresponding to the zabbix sender protocol data field
                            - each has 'host' (zabbix host), 'key' (key of the item) and 'value' (value to push to the item).
                            The function returns a list in case one AWS metric translates to more Zabbix metrics,
                            e.g. the Duration metric may translate to max.duration and min.duration in zabbix, 
                            thus the function returns two dictionaries
    '''
    sender_data = [
                list(map(lambda e: e.update({'clock': json['timestamp']}),
                     zbx_sender_data(json['metric_name'],json['value'],json['dimensions']['FunctionName'])))
                for json in jsons] # get data objects for each metric and function, and update the objects with clock parameter
    sender_data = list(i.chain(*sender_data))


    return j.dumps(
        {
            "request":"sender data",  # zabbix_sender request to zabbix server -- only trapper items are used
            "data": sender_data
        }
    ).encode("utf-8") # encode to bytes object for socket

def zbx_send_packet(addr:Tuple[str,str],data: bytes):
    s=socket.create_connection(addr)
    s.sendall(b"ZBXD\1" + struct.pack("<II",len(data),0) + data)
    o = s.recv(1024)
    s.close()
    return o