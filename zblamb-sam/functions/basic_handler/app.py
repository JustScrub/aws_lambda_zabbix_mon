
import os, logging
from utils import extract_data, zbx_discover_packet, zbx_mass_item_packet, zbx_send_packet, ZBX_SUFFIX
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'WARNING').upper())

def lambda_handler(e,c):
    logger.info("Event %s",e)
    zbx_addr = (os.environ['ZBLAMB_PROXY_IP'],10051)

    # extract metrics
    data = extract_data(e)

    # discover functions
    packet, ignored_functions = zbx_discover_packet(ZBX_SUFFIX,data)
    logger.info("Discovery packet: %s",packet)
    resp = zbx_send_packet(zbx_addr,packet)
    logger.info("Discovery response: %s",resp)

    # send metrics to Zabbix
    packet = zbx_mass_item_packet(data,ZBX_SUFFIX,ignored_functions)
    logger.info("Item packet: %s",packet)
    resp = zbx_send_packet(zbx_addr,packet)
    logger.info("Item response: %s",resp)

    return {'records': [{'recordId': r['recordId'],'result': 'Dropped','data': ''} for r in e['records']]} # drop all data, do not send it further via firehose