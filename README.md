# Zabbix Lambda Monitoring
Monitoring AWS lambdas using Zabbix


Architecture:
 - AWS side --> this project --> Zabbix side
 - AWS Lambda --> AWS CloudWatch --> metrics to this project --> Zabbix Proxy --> Zabbix Server --> Dashboard

# TODO
 - Setup Metric Stream
    - namespace: AWS/Lambda, metric: Error
    - Firehose source = DirectPUT, output based on one of approaches
    - CloudWatch sends accumulated metrics per 60 seconds, Firehose buffers incomming data for specified duration (Minimum = 60 min | 1MB data)
    - CloudWatch -> Firehose -> S3 bucket -> Lambda -> Zabbix Protocol -> Zabbix Proxy
        - Lambda:
            - downloads the metric JSON file, finds metrics per function name dimension ONLY -- one row = one json
            - gets ".values.sum" and ".timestamp"
            - sends Zabbix packet to a Zabbix proxy
                - contains: specific zabbix hostname (e.g. zabbix-lambda-errors), function name and "values.sum", timestamp
    - CloudWatch -> Firehose -> HTTPS Endpoint -> Zabbix protocol -> Zabbix Proxx
        - HTTPS Endpoint must have public IP address
        - Firehose cannot currently access instances in a private VPC subnet
            - https://docs.aws.amazon.com/firehose/latest/dev/controlling-access.html#using-iam-http

    - CloudWatch -> Firehose -> Transformation Lambda -> "S3" / any other destination
        - Transformation Lambda:
            - is in VPC with Zabbix Proxy/Server -- can be private!
            - takes data "to transform"
            - only extracts ".values.sum", ".timestamp" and ".dimensions.functionName" (from jsons with single dimension)
            - sends extracted data to Zabbix Proxy/Server with a specific zabbix hostname (e.g. zabbix-lambda-errors) in a Zabbix packet
            - returns ``{"recordID": "provided ID by Firehose", "result": "Dropped", "data": ""}`` to Firehose
                - Firehorse does not pass it forward to the destination

 - configure Zabbix
    - add host (e.g. zabbix-lambda-errors)
    - possible flows:
        - aggregate functions
            - add trapper items to the host:
                - error-stream: text entries, just a stream of AWS Lambda names that failed (with the correct number of failures from CloudWatch)
                - error-log: log entries, contains severity, function name and number of failed invocations
                - error-counts: number entries, just a number of failures, aggregated across all Lambda functions
                - error-count-string: text entries, comma-delimited repetition of FnName, number of repetitions is number of failures
            - create a trigger based on at least one of the items
                - which ones? How to show the Function Name in Dashboard? Are neccessary operations/function implemented in Zabbix trigger expressions?
                    - `error-counts.count(1H, threshold, ge) > 1` --> "A Lambda keeps failing. Go to logs for more information"
                    - `error-count-string.count(1H, "([A-Za-z0-9]+),\1,\1",regex)>1` --> "A lambda keeps failing. Go to logs..."
                        - repeat `\1` threshold-times
                - or create multiple triggers for items? Per-Lambda trigger?
                    - `error-stream.count(1H, FnName, eq) > threshold` --> "Lambda FnName keeps failing"
                    - <b>Automatization of Lambda Registration</b>

        - Per-Lambda trapper items
            - just error-counts (e.g. FnName.error-counts item) would suffice
            - trigger: `FnName.error-counts.count(1H, threshold, ge)>1` --> "Lambda FnName keeps failing"
            - <b>Automatization of Lambda Registration</b>
    - somehow visualize
    - maybe change docker images to CentOS? Since the instances run on Amazon Linux, based off CentOS?
 
 - Migrate from pure CloudFormation to SAM 

 - create network stack:
    - VPC + IGW + NATGW
    - Public Subnet + Private Subnet + Routing tables for both
    - VPC endpoint (AWS PrivateLink) for Firehose

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
    - CloudFormation create: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-metric-streams-setup-datalake.html#CloudWatch-metric-streams-setup-datalake-CFN
    - CloudFormation object:  https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cloudwatch-metricstream.html

 - Data Firehose:
    - basic create: https://docs.aws.amazon.com/firehose/latest/dev/basic-create.html
    - CloudFormation object: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kinesisfirehose-deliverystream.html
    - HTTP Endpoint destination: https://docs.aws.amazon.com/firehose/latest/dev/create-destination.html#create-destination-http
    - Destination in private VPC subnet: https://docs.aws.amazon.com/firehose/latest/dev/vpc.html

 - PrivateLinks:
    - basics: https://docs.aws.amazon.com/vpc/latest/privatelink/what-is-privatelink.html

 - Zabbix API -- version 5.0!
    - overview: https://www.zabbix.com/documentation/5.0/en/manual/api

 - Zabbix Trapper + Sender
    - https://www.zabbix.com/documentation/5.0/en/manual/config/items/itemtypes/trapper
    - https://pypi.org/search/?q=%22zabbix+sender%22&o=-created

 - Zabbix Docker images -- version 5.4 (ubuntu)
    - frontend (Nginx + Postgres): https://hub.docker.com/r/zabbix/zabbix-web-nginx-pgsql
    - server (Postgres): https://hub.docker.com/r/zabbix/zabbix-server-pgsql
    - proxy (SQLite3): https://hub.docker.com/r/zabbix/zabbix-proxy-sqlite3
    - agent: https://hub.docker.com/r/zabbix/zabbix-agent
    - postgres: https://hub.docker.com/layers/library/postgres/13-alpine/images/sha256-0ee5d31fd23e9c749cdaba1e203512ffec8420791e561489d6ab7b038c5d75a0