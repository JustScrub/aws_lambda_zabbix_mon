
import os, logging
from utils import extract_data, zbx_discover_packet, zbx_mass_item_packet, zbx_send_packet, ZBX_SUFFIX
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'WARNING').upper())

metric2stat_map = { # map metric to desired statistic. See Lambda Metrics AWS documentation for more info. Available: sum, count, min, max
    "Errors": ["sum"], # values must be lists
    "Duration": ["max", "min"] # more values = push several statistics of 1 metric to Zabbix, items of metrics are <statistic>.<metric>.metrics.<host>[<function_name>]
}

zabbix_host = ZBX_SUFFIX
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
    logger.info("Event %s",e)
    zbx_addr = (os.environ['ZBLAMB_PROXY_IP'],10051)

    # extract metrics
    data = extract_data(e)

    # discover functions
    packet, ignored_functions = zbx_discover_packet(zabbix_host,data)
    logger.info("Discovery packet: %s",packet)
    resp = zbx_send_packet(zbx_addr,packet)
    logger.info("Discovery response: %s",resp)

    # send metrics to Zabbix
    packet = zbx_mass_item_packet(data,sender_data,ignored_functions)
    logger.info("Item packet: %s",packet)
    resp = zbx_send_packet(zbx_addr,packet)
    logger.info("Item response: %s",resp)

    return {'records': [{'recordId': r['recordId'],'result': 'Dropped','data': ''} for r in e['records']]} # drop all data, do not send it further via firehose