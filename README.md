# Zabbix Lambda Monitoring
Monitoring AWS lambdas using Zabbix


# TODO
 - test template functionality
 - create network stack:
    - VPC, public and private network inside VPC
    - use instance in public network as NAT gateway for private subnet: 
        - https://medium.com/nerd-for-tech/how-to-turn-an-amazon-linux-2023-ec2-into-a-nat-instance-4568dad1778f
        - Setup Elastic Network Interface -> add to private subnet (gains private IP from it) -> attach to EC2 instance within public subnet
        - set NAT: inbound NWI to translated outbound eth and vice versa, allow normal traffic on eth

                iptables -t nat -A POSTROUTING -o <pub_IF> -s <VPC CIDR range> -p tcp -j MASQUERADE --to-ports 10000-20000
                iptables -t nat -A POSTROUTING -o <pub_IF> -s <VPC CIDR range> -p udp -j MASQUERADE --to-ports 10000-20000
                iptables        -A FORWARD     -i <prv_IF> -s <VPC CIDR range>        -j ACCEPT

        - Private routing table entry: Outbound 0.0.0.0/0 to NWI.IP
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