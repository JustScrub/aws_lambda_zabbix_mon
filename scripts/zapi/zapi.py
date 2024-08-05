import sys, os
from .zapi_constructor import *
from .. import config
from ...metrics_def import MetricConfigs

def imdsv2_get_local_addr():
    import requests
    tok = requests.request(
        method="PUT",
        url="http://169.254.169.254/latest/api/token",
        headers={ 'X-aws-ec2-metadata-token-ttl-seconds': 10, "content-type": "application/json"}
    )
    ip = requests.request(
        method="GET",
        url="http://169.254.169.254/latest/meta-data/local-ipv4",
        headers={'X-aws-ec2-metadata-token': tok.text, "content-type": "application/json"}
    )
    return ip.text

def configure_zabbix_from_agent(zapi:ZabbixAPI, metrics:List[LLDMultiTriggerMetricConfig], proxy_addr:Tuple[str,int], local_addr:Tuple[str,int]=None):
    local_addr = local_addr or (imdsv2_get_local_addr(),10050)

    proxy_id=create_proxy(zapi,
                 "zblamb",
                 interface_dict(
                     addr=proxy_addr[0],
                     port=proxy_addr[1]
                 ),
                 active=False
    )
    
    group_id=create_group(zapi,"zblamb")
    host_id=create_host(
        zapi,
        config.ZBX_SUFFIX,
        [group_id],

        proxy_hostid=proxy_id,
        interfaces=[
            interface_dict(
                addr=local_addr[0],
                port=local_addr[1]
            )
        ]
    )

    create_multi_trigger_mapping(
        zapi,
        metrics,
        config.ZBX_SUFFIX,
        config.ZBX_PRIO_MACRO,
        config.ZBX_FN_NAME_MACRO,
        group_id=group_id,
        host_id=host_id
    )

def configure_zabbix_from_server(zapi:ZabbixAPI,metrics:List[LLDMultiTriggerMetricConfig]):
    group_id=create_group(zapi,"zblamb")
    host_id=create_host(
        zapi,
        config.ZBX_SUFFIX,
        [group_id],
    )

    create_multi_trigger_mapping(
        zapi,
        metrics,
        config.ZBX_SUFFIX,
        group_id=group_id,
        host_id=host_id
    )

if __name__ == "__main__":

    frontend_host=sys.argv[1] if len(sys.argv)>1 else os.environ.get("ZBLAMB_FRONTEND_HNAME","localhost")
    frontend_port=sys.argv[2] if len(sys.argv)>2 else 80
    try:
        frontend_port=int(frontend_port)
    except:
        print("Invalid frontend port: must be number!")
        exit(1)
    url=f"http://{frontend_host}:{frontend_port}"

    zapi = ZabbixAPI(url)
    zapi.login("Admin", "zabbix")

    #metrics = [
    #    LLDMultiTriggerMetricConfig(
    #        zbx_name="errors",
    #        zbx_value_type="int",
    #        zbx_trigger_expression_pattern='count({},5m,"ge","{}")>=1',
    #        aws_metric_name='Errors',
    #        aws_statistic_name='sum',
    #        priority_mapping={
    #            LambdaPriority(0): { ZabbixSeverity.DISASTER: 1 },                                                      # prio 0 triggers disaster on at least one fail
    #            LambdaPriority(1): { ZabbixSeverity.DISASTER: 2,   ZabbixSeverity.HIGH: 1},                             # prio 1 triggers disaster on at least 2 fails and high on 1 fail
    #            LambdaPriority(2): { ZabbixSeverity.DISASTER: None,ZabbixSeverity.HIGH: 2, ZabbixSeverity.AVERAGE: 1},  # prio 2 triggers high on at least 2 fails and average on 1 fail
    #            LambdaPriority(-1): {severity: None for severity in list(ZabbixSeverity)}                               # undefined priority does not trigger anything
    #        }
    #    )
    #]

    metrics = MetricConfigs

    if len(sys.argv)>3 and sys.argv[3]=="agent":
        configure_zabbix_from_agent(
            zapi,
            metrics,
            (os.environ["ZBLAMB_PROXY_IP"],10051)
        )
    elif len(sys.argv)>3 and sys.argv[3]=="server":
        configure_zabbix_from_server(zapi,metrics)
    else:
        create_multi_trigger_mapping(zapi,metrics,
                                     suffix=config.ZBX_SUFFIX,
                                     prio_tag=config.ZBX_PRIO_MACRO,
                                     name_tag=config.ZBX_FN_NAME_MACRO,
                                     group_id=19)