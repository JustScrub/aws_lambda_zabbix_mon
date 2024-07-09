# Zabbix Lambda Monitoring
Monitoring AWS lambdas using Zabbix


# TODO
 - Setup Metric Stream
    - namespace: AWS/Lambda, metric: Error
    - CloudWatch -> Firehose -> S3 bucket -> Lambda -> Zabbix Protocol -> Zabbix Proxy
    - CloudWatch sends accumulated metrics per 60 seconds, Firehose buffers incomming data for specified duration (Minimum = 60 min | 1MB data)
    - Lambda:
     - downloads the metric JSON file, finds metrics per function name dimension ONLY -- one row = one json
     - gets ".values.sum" and ".timestamp"
     - sends Zabbix packet to a Zabbix proxy
        - contains: specific zabbix hostname (e.g. zabbix-lambda-errors), function name and "values.sum", timestamp

 - configure Zabbix
    - add custom template/metric -- for incomming packets from lambda
    - add lambda hostname (e.g. zabbix-lambda-errors) to a proxy, allow all IP addresses
    - somehow visualize
    - maybe change docker images to CentOS? Since the instances run on Amazon Linux, based off CentOS?
 
 - create network stack:
    - VPC + IGW + NATGW
    - Public Subnet + Private Subnet + Routing tables for both

# Done
 - test template functionality
 - test scripts functionality
 - configure Zabbix 
    - passive agent --> proxy --> server
    - agent:
        - `Hostname` (for server/proxy) config already set via compose
            - and also not needed for passive checks
            - zblamb-agent
        - `Server` config already set via compose to proxy's private IP
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

# Useful links
 - AWS instances
    - manage metadata: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-metadata-v2-how-it-works.html
    - manage ENI with EC2 instance: https://www.reddit.com/r/aws/comments/m08tsc/comment/gq6px8g/

 - Metric streams
    - Basics: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-metric-streams-setup.html
    - CloudFormation:  https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cloudwatch-metricstream.html

 - Zabbix API -- version 5.0!
    - overview: https://www.zabbix.com/documentation/5.0/en/manual/api

 - Zabbix Docker images -- version 5.4 (ubuntu)
    - frontend (Nginx + Postgres): https://hub.docker.com/r/zabbix/zabbix-web-nginx-pgsql
    - server (Postgres): https://hub.docker.com/r/zabbix/zabbix-server-pgsql
    - proxy (SQLite3): https://hub.docker.com/r/zabbix/zabbix-proxy-sqlite3
    - agent: https://hub.docker.com/r/zabbix/zabbix-agent
    - postgres: https://hub.docker.com/layers/library/postgres/13-alpine/images/sha256-0ee5d31fd23e9c749cdaba1e203512ffec8420791e561489d6ab7b038c5d75a0