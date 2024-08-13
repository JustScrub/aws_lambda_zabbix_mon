import sys, os
from .zapi_constructor import *
from .. import config
from scripts.metrics_def import MetricConfigs

def imdsv2_get_local_addr():
    import requests
    tok = requests.request(
        method="PUT",
        url="http://169.254.169.254/latest/api/token",
        headers={ 'X-aws-ec2-metadata-token-ttl-seconds': "10", "content-type": "application/json"}
    )
    ip = requests.request(
        method="GET",
        url="http://169.254.169.254/latest/meta-data/local-ipv4",
        headers={'X-aws-ec2-metadata-token': tok.text, "content-type": "application/json"}
    )
    return ip.text

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

def configure_zabbix_server_proxy(zapi:ZabbixAPI,metrics:List[LLDMultiTriggerMetricConfig], proxy_name):
    proxy_id = zapi.proxy.get(
            search={
                "host": proxy_name
            },
            output=['proxyid']
    ) # [ {"proxyid": '10478'}, ... ]    --> empty list = no proxy found

    if not proxy_id:
        proxy_id=create_proxy(zapi,
                    config.ZBX_SUFFIX,
                    interface_dict(
                        addr=proxy_name,
                        port=10051
                    ),
                    active=False
        )
    else:
        proxy_id = proxy_id[0]["proxyid"]

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
        print("\t\t\t Proxy must be specified in the fourth argument. You can either specify zabbix host name of the proxy, if it already exists in zabbix, or IP address/DNS name of the proxy, listening on port 10051, and it will be created in Zabbix as Passive Proxy")

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

    if len(sys.argv)>3 and sys.argv[3]=="server":
        configure_zabbix_server(zapi,metrics)
    elif len(sys.argv)>3 and sys.argv[3]=="proxy":
        try:
            proxy_name = sys.argv[4] 
        except:
            print("You must provide proxy name in Zabbix or proxy IP!")
            exit(1)
        configure_zabbix_server_proxy(zapi,metrics,proxy_name)
    else:
        create_multi_trigger_mapping(zapi,metrics,
                                     suffix=config.ZBX_SUFFIX,
                                     prio_tag=config.ZBX_PRIO_MACRO,
                                     name_tag=config.ZBX_FN_NAME_MACRO,
                                     group_id=19)