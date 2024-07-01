# Zabbix Lambda Monitoring
Monitoring AWS lambdas using Zabbix


# TODO
 - test template functionality
 - test scripts functionality
 - configure Zabbix 
    - passive agent --> proxy --> server
    - agent:
        - `Hostname` (for server/proxy) config already set via cmd
            - and also not needed for passive checks
            - zblamb-agent
        - `Server` config already set via cmd to proxy's private IP
    - proxy:
        - configure: https://www.zabbix.com/documentation/current/en/manual/appendix/config/zabbix_proxy
        - docker image: https://hub.docker.com/r/zabbix/zabbix-proxy-sqlite3
        - `Server` config already set to server's private IP
        - `Hostname` config set to zblamb-proxy
    - server:
        - add passive proxy:  (hostname, passive mode, interface)
        - add host group
        - add host monitored by proxy
        - add template to host
        - https://www.zabbix.com/documentation/current/en/manual/distributed_monitoring/proxies