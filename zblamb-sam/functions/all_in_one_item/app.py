from utils import extract_data, zbx_item_packet, zbx_send_packet
import os

zabbix_host = "all-in-one.lambda.zblamb"
def sender_data(metric, values, FunctionName):
    if metric != 'Errors': return [] # only error metric for all-in-one item
    
    Value = values['sum']
    suf = f"metrics.{zabbix_host}"
    return [
        *([ 
            { 
                "host":zabbix_host,
                "key":f"error-stream.{suf}",
                "value":FunctionName } 
            ] * Value), # error-stream: for each error, sends name of the failed function
        {
            "host":zabbix_host,
            "key":f"error-log.{suf}",
            "value":f"ERROR {Value} {FunctionName}"
        }, # logs number of errors for a function
        {
            "host":zabbix_host,
            "key":f"error-counts.{suf}",
            "value":f"{Value}"
        }, # just sends number of failures, without lambda name
        {
            "host":zabbix_host,
            "key":f"error-count-string.{suf}",
            "value":','.join([FunctionName]*Value)
        } # "unary"-base number of failures, "digits" are name of the function and are separated by a comma
            # e.g. 'Lambda1,Lambda1,Lambda1' -- the function 'Lambda1' failed 3 times
    ]


def lambda_handler(e,c):
    print(e)
    zbx_addr = (os.environ['ZBLAMB_PROXY_IP'],10051)

    data = extract_data(e)
    packet = zbx_item_packet(data,sender_data)
    resp = zbx_send_packet(zbx_addr,packet)
    print(resp)
    return {'records': [{'recordId': r['recordId'],'result': 'Dropped','data': ''} for r in e['records']]} # drop all data, do not send it further via firehose