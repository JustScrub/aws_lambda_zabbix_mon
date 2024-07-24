
import os
from utils import extract_data, zbx_discover, zbx_item_packet, zbx_send_packet

metric2stat_map = { # map metric to desired statistic. See Lambda Metrics AWS documentation for more info. Available: sum, count, min, max
    "Errors": ["sum"], # values must be lists
    "Duration": ["max", "min"] # more values = push several statistics of 1 metric to Zabbix, items of metrics are <statistic>.<metric>.metrics.<host>[<function_name>]
}

zabbix_host = "multi.lambda.zblamb"
def sender_data(metric,values,function_name):
    stats = metric2stat_map[metric]
    return [
        {
            "host": zabbix_host,
            "key": f"{stat+'.' if len(stats)>1 else ''}{metric.lower()}.metrics.{zabbix_host}[{function_name}]",
            "value": values[stat]
        }
        for stat in stats
    ]

def lambda_handler(e,c):
    print("Event",e)
    print("Context",c)
    zbx_addr = (os.environ['ZBLAMB_PROXY_IP'],10051)

    data = extract_data(e)
    resp, untracked = zbx_discover(zbx_addr,zabbix_host,data)
    print("Discovery response:",resp)
    packet = zbx_item_packet(data,sender_data,untracked)
    resp = zbx_send_packet(zbx_addr,packet)
    print(resp)

    return {'records': [{'recordId': r['recordId'],'result': 'Dropped','data': ''} for r in e['records']]} # drop all data, do not send it further via firehose