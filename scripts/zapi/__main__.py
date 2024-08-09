import sys, os
from .zapi_constructor import *
from .. import config
from scripts.metrics_def import MetricConfigs

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

def configure_zabbix_server_proxy_agent(zapi:ZabbixAPI, metrics:List[LLDMultiTriggerMetricConfig], proxy_addr:Tuple[str,int], local_addr:Tuple[str,int]=None):
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

def configure_zabbix_server(zapi:ZabbixAPI,metrics:List[LLDMultiTriggerMetricConfig]):
    group_id=create_group(zapi,config.ZBX_SUFFIX)
    host_id=create_host(
        zapi,
        config.ZBX_SUFFIX,
        [group_id],
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

def configure_zabbix_server_proxy(zapi:ZabbixAPI,metrics:List[LLDMultiTriggerMetricConfig], proxy_addr):
    if not proxy_addr[0]:
        proxy_addr = (imdsv2_get_local_addr(),10050)
    proxy_id=create_proxy(zapi,
                 config.ZBX_SUFFIX,
                 interface_dict(
                     addr=proxy_addr[0],
                     port=proxy_addr[1]
                 ),
                 active=False
    )
    group_id=create_group(zapi,config.ZBX_SUFFIX)
    host_id=create_host(
        zapi,
        config.ZBX_SUFFIX,
        [group_id],
        proxy_hostid=proxy_id,
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

if __name__ == "__main__":

    if len(sys.argv) and sys.argv[1] == "help":
        print("Usage: python3 -m scripts.zapi [frontend_host=localhost] [frontend_port=80] [configuration]")
        print("\tfrontend_host, frontend_port: IP or DNS name and port of Zabbix frontend")
        print("\tconfiguration: special configuration for server-only or server+proxy. If omitted, does the same as server configuration")
        print("\t\t server: create host group, host with LLD rule and configure the host based on specified metrics in metrics_def.py")
        print("\t\t proxy: create host group, proxy and host with LLD rule managed by the proxy and configure the host based on metrics_def.py")
        print("\t\t\t to specify proxy IP or DNS name, use ZBLAMB_PROXY_IP environment variable or pass it as a fourth argument")

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

    metrics = MetricConfigs

    if len(sys.argv)>3 and sys.argv[3]=="agent":
        local_addr = (os.getenv("ZBLAMB_AGENT_IP"),10050) if "ZBLAMB_AGENT_IP" in os.environ else None
        configure_zabbix_server_proxy_agent(
            zapi,
            metrics,
            (os.environ["ZBLAMB_PROXY_IP"],10051),
            local_addr
        )
    elif len(sys.argv)>3 and sys.argv[3]=="server":
        configure_zabbix_server(zapi,metrics)
    elif len(sys.argv)>3 and sys.argv[3]=="proxy":
        proxy_ip = sys.argv[4] if len(sys.argv) > 4 else os.getenv("ZBLAMB_PROXY_IP")
        configure_zabbix_server_proxy(zapi,metrics,(proxy_ip,10051))
    else:
        create_multi_trigger_mapping(zapi,metrics,
                                     suffix=config.ZBX_SUFFIX,
                                     prio_tag=config.ZBX_PRIO_MACRO,
                                     name_tag=config.ZBX_FN_NAME_MACRO,
                                     group_id=19)