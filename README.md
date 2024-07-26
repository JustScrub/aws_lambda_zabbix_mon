# Zabbix Lambda Monitoring
Monitoring AWS lambdas using Zabbix


Architecture:
 - AWS side --> this project --> Zabbix side
 - AWS Lambda --> AWS CloudWatch --> metrics to this project --> Zabbix Proxy --> Zabbix Server --> Dashboard

# Config
 - Zabbix: 
    - zabbix-scripts/zapi.py
        - select mapping (all-in-one item, single-trigger discovery, multi-trigger discovery)
        - create list of MetricConfig objects for the specific mapping
            - there can be multiple zabbix items/metrics for one metric in AWS Lambda
            - each is a separate instance of MetricConfig
        - call function that populates zabbix

 - AWS: 
    - zblamb-sam/
        - template.yaml
            - includes demo infrastructure, feel free to modify (remove EC2 instance...)
            - only Firehose transform Lambda, Firehose Data Stream and Meric Stream objects must remain
                - Transform Lambda must have ZBLAMB_PROXY_IP environment variable defined!
                - IP address of the Zabbix Server/Proxy it will be sending data to
                - if the Zabbix Server/Proxy is in a private subnet in AWS VPC, the transform lambda must be "inside" as well
            - in Metric Stream, select which metric for Lambda to stream (e.g. 'Errors', 'Duration')
            - can add more statistics (see AWS::CloudWatch::MetricStream documentation)

        - functions/
            - modify python function that generates Zabbix Sender items or modify variables used inside (e.g. `metric2stat_map` in multi_trigger_transform/app.py)
                - the function recieves AWS metric name, dictionary of {statistic: value} and function name
                - dictionary of statistics includes default statistics (min,max,sum,count) and those specified in template.yaml under Metric Stream
                - returns <b>List</b> of dictionaries `{'host':zabbix host, 'key': item key, 'value': zabbix metric value}`
                - The list may include more dictionaries, if one AWS metric produces more zabbix items/metrics
                    - e.g. Zabbix may track the min and max statistic of the Duration AWS metric
                    - the list would contain two such dictionaries, one with value equal to min and one with max
                    - Zabbix items must be different as well
                - <b>This function maps AWS metrics to Zabbix metrics</b>
                - you can create whatever mapping you wish, Zabbix just has to be configured for it (have items and tiggers, LLD rules, etc.)

- Common:
    - all 'names' (e.g. Zabbix item names, Zabbix host names or trigger names) must be same across Zabbix and AWS config!
        - main idea: the Zabbix host that manages its stuff has a 'simple' name or 'suffix', on which all other names are based
        - all zabbix names are lower-case, except for Lambda function name (anything outside of `[]` is lower-case)
        - LLD rule under the host has (item) name `discovery.<suffix>`
        - items have name `<zabbix_metric>.metrics.<suffix>[<function_name>]` (or without `[]` part for non-discovery, e.g. all-in-one item)
            - if one AWS metric has more statistics tracked by zabbix, the convention would be `<statistic>.<aws_metric>.metrics.<suffix>[<function_name>]`, e.g. `max.duration.metrics.multi-trigger-mapping-zblamb[{#FN_NAME}]` for item prototype
            - multi_trigger_transform AWS lambda function counts on this
            - but it's always up to you :-)
        - triggers have name `<severity>.<zabbix_metric>.triggers.<suffix>[<function_name>]` or without `<severity>` for other than multi-trigger mapping and without `[]` for non-discovery
        - proxy has name `proxy.<suffix>`
        - host group has name `group.<suffix>` 


# TODO
 - Resolve problems:
    - Zabbix triggers wrong severity sometimes
    - Changing priority of Lambda
    - Do not send discovery of all lambdas from Transform Lambda
        - only not yet discovered
        - cache discovered lambdas
    - "Time consistency"
        - Parallel transform Lambda invocations -- allow or not?
            - disable by setting Lambda timeout same as Firehose Buffering -- may be triggered early by size buffering setting
        - out-of-order delivery on Zabbix
            - Lambda invocation 0 has connectivity problems
            - Lambda invocation 1 delivers metrics to Zabbix
            - invocation delivers metrics -- after invoc 1! 
            - Earlier metrics delivered later than current latest metrics
            - Clock param of Zabbix Trapper protocol?

 - Benchmark the infrastructure:
    - 1000 active instances at once (at all times?)
    - Transform lambda duration, parallelism?
    - figure out good parameters -- Firehose buffering time and size, Lambda timeout, ...
    - mock Firehose? (Not to have actual 1000 lambda instances running at once all the time)

 - Central config for AWS and Zabbix

 - create readable doc for the project

 - Setup Metric Stream
    - CloudWatch -> Firehose -> Transformation Lambda -> "S3" / any other destination
        - send 1 packet to Zabbix per 1 metric stream record (not all at once) -- for correct timestamps

 - configure Zabbix
    - maybe change docker images to CentOS? Since the instances run on Amazon Linux, based off CentOS?

 - Change paths of IAM roles
 
 - move templates to SAM

 - create network stack:
    - VPC + IGW + NATGW
    - Public Subnet + Private Subnet + Routing tables for both
    - VPC endpoint (AWS PrivateLink) for Firehose

# Done
 - Setup Metric Stream:
    - namespace: AWS/Lambda, metric: Error
    - Firehose source = DirectPUT, output based on one of approaches
    - CloudWatch sends accumulated metrics per 60 seconds, Firehose buffers incomming data for specified duration (Minimum = 60 min | 1MB data)
    - CloudWatch -> Firehose -> Transformation Lambda -> "S3" / any other destination
        - Transformation Lambda:
            - is in VPC with Zabbix Proxy/Server -- can be private!
            - takes data "to transform"
            - only extracts ".values.sum", ".timestamp" and ".dimensions.functionName" (from jsons with single dimension)
            - sends extracted data to Zabbix Proxy/Server with a specific zabbix hostname (e.g. zabbix-lambda-errors) in a Zabbix packet
            - returns ``{"recordID": "provided ID by Firehose", "result": "Dropped", "data": ""}`` to Firehose
                - Firehorse does not pass it forward to the destination

 - configure Zabbix infrastructure
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

 - configure Zabbix metrics
    - add host zblamb-lambda-errors
        - no interface
    - possible flows:
        - aggregate functions
            - add trapper items to the host:
                - error-stream: text entries, just a stream of AWS Lambda names that failed (with the correct number of failures from CloudWatch)
                - error-log: log entries, contains severity, function name and number of failed invocations
                - error-counts: number entries, just a number of failures, aggregated across all Lambda functions
                - error-count-string: text entries, comma-delimited repetition of FnName, number of repetitions is number of failures
            - create a trigger based on at least one of the items
                - `count(/zblamb-lambda-errors/error-count-string, 5m, "([A-Za-z0-9]+),\1,\1",regex)>0` --> "A lambda keeps failing"
                    - Tags: Key="Lambda Name", Value=` "{{ITEM.VALUE}.regsub(\"([A-Za-z0-9]+),\\1,\\1\", \"\\1\")}" `
                    - Allow multiple triggers with correlation tag "Lambda Name"
                    - Allow manual close
                    - These setting wills report errors per-function
        - Single-Host Multi-Trigger Per-Lambda trapper items via Low-Level Discovery
            - Lambdas are tagged in AWS with a prioirty, e.g. `{PRIO=0}`
            - host + discovery rule with key e.g. `discover.lambda.aws`
            - mapping between Lambda priorities and Zabbix severities
                - each Lambda priority maps to multiple Zabbix severities (or rather triggers)
                - configuration: 2D table Lambda priorities × Zabbix severities, entries = Constants for triggers
                    - constants say when a trigger for corresponding severity should trigger (for a function with corresponding priority)
                    - can leave out some entries = the priority does not trigger the left out severity
            - host macros
                - for each metric and each severity, create macros with context
                - context = lambda priority
                - value = configuration table entry for that severity/priority
                    - `PRIO=0` => `{#ERRORS_HIGH:0}=4`, `{#ERRORS_AVERAGE:0}=2`, `{#ERRORS_INFO:0}=1`
                    - `PRIO=3` => `{#ERRORS_AVERAGE:3}=5`, `{#ERRORS_INFO:3}=1`
                - do not create macros for left out entries
                - each macro has a default value (without context) for non-classified functions (not known or no priority)
                    - to "disable" these, put high number
            - item prototypes
                - for each metric, parametrized by function e.g. `error.metrics.lambda.aws[${FN_NAME}]`/`duration.metrics.lambda.aws[${FN_NAME}]`
            - trigger prototypes
                - create for each item and each Zabbix priority one trigger
                    - e.g. `INFO.error.metrics.lambda.aws[${FN_NAME}]`/`AVERAGE.duration.metrics.lambda.aws[${FN_NAME}]`
                - all triggers have same expression, just the constants differ
                    - `count(/lambda.aws/errors.metrics.lambda.aws[{#FN_NAME}],5m,"ge","{$ERROR_INFO:{#PRIO}}")>=1`    
                    - `count(/lambda.aws/errors.metrics.lambda.aws[{#FN_NAME}],5m,"ge","{$ERROR_HIGH:{#PRIO}}")>=1`
                - do not create triggers for left out entries in the configuration table
                    - using discovery rule Overrides

        - Single-Host Single-Trigger Per-Lambda trapper items via Low-Level Discovery
            - like Multi-Trigger, but simpler
            - config: two simple mappings Lambda Priority -> Zabbix Severity, Lambda Priority -> Constant Value
            - macros: for each metric and priority (with context), not for severities, according to Priority -> Constant mapping
            - item prototypes: same as Multi-Trigger
            - trigger prototypes:
                - one trigger per item
                - using discovery rule Overrides, change the severity during discovery to the one corresponding to Priority -> Severity mapping
            - Priority -> Severity mapping tells what severity that priority has
            - Priority -> Constant mapping tells when the trigger with that severity should set off


# Abandoned Ideas
 - Setup Metric Stream:
    - CloudWatch -> Firehose -> S3 bucket -> Lambda -> Zabbix Protocol -> Zabbix Proxy/Server
        - Lambda:
            - downloads the metric JSON file, finds metrics per function name dimension ONLY -- one row = one json
            - gets ".values.sum" and ".timestamp"
            - sends Zabbix packet to a Zabbix proxy
                - contains: specific zabbix hostname (e.g. zabbix-lambda-errors), function name and "values.sum", timestamp
    - CloudWatch -> Firehose -> HTTPS Endpoint -> Zabbix protocol -> Zabbix Proxy
        - HTTPS Endpoint must have public IP address
        - Firehose cannot currently access instances in a private VPC subnet
            - https://docs.aws.amazon.com/firehose/latest/dev/controlling-access.html#using-iam-http

# Useful links
 - AWS instances
    - manage metadata: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-metadata-v2-how-it-works.html
    - manage ENI with EC2 instance: https://www.reddit.com/r/aws/comments/m08tsc/comment/gq6px8g/

 - AWS Managed Policies:
    - list: https://docs.aws.amazon.com/aws-managed-policy/latest/reference/policy-list.html
    - Lambda Basic Executions: https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AWSLambdaBasicExecutionRole.html
    - Lambda VPC permissions: https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AWSLambdaVPCAccessExecutionRole.html

 - Metric streams
    - Basics: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-metric-streams-setup.html
    - CloudFormation create: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-metric-streams-setup-datalake.html#CloudWatch-metric-streams-setup-datalake-CFN
    - CloudFormation object:  https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cloudwatch-metricstream.html

 - Data Firehose:
    - basic create: https://docs.aws.amazon.com/firehose/latest/dev/basic-create.html
    - CloudFormation object: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kinesisfirehose-deliverystream.html
    - HTTP Endpoint destination: https://docs.aws.amazon.com/firehose/latest/dev/create-destination.html#create-destination-http
    - Destination in private VPC subnet: https://docs.aws.amazon.com/firehose/latest/dev/vpc.html
    - IAM roles: https://docs.aws.amazon.com/firehose/latest/dev/controlling-access.html

 - PrivateLinks:
    - basics: https://docs.aws.amazon.com/vpc/latest/privatelink/what-is-privatelink.html

 - Zabbix API -- version 5.0!
    - overview: https://www.zabbix.com/documentation/5.0/en/manual/api

 - Zabbix Low-Level Discovery
    - basic: https://www.zabbix.com/documentation/5.4/en/manual/discovery/low_level_discovery
    - user macros with context: https://www.zabbix.com/documentation/5.4/en/manual/config/macros/user_macros_context#use-cases
    - tutorial: https://blog.zabbix.com/how-to-use-zabbix-low-level-discovery/9993#custom-low-level-discovery-rul

 - Zabbix Trapper + Sender
    - https://www.zabbix.com/documentation/5.0/en/manual/config/items/itemtypes/trapper
    - https://pypi.org/search/?q=%22zabbix+sender%22&o=-created

 - Zabbix Docker images -- version 5.4 (ubuntu)
    - frontend (Nginx + Postgres): https://hub.docker.com/r/zabbix/zabbix-web-nginx-pgsql
    - server (Postgres): https://hub.docker.com/r/zabbix/zabbix-server-pgsql
    - proxy (SQLite3): https://hub.docker.com/r/zabbix/zabbix-proxy-sqlite3
    - agent: https://hub.docker.com/r/zabbix/zabbix-agent
    - postgres: https://hub.docker.com/layers/library/postgres/13-alpine/images/sha256-0ee5d31fd23e9c749cdaba1e203512ffec8420791e561489d6ab7b038c5d75a0