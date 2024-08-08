# Zabbix Lambda Monitoring
Monitoring AWS lambdas using Zabbix

Architecture:
 - AWS side --> this project --> Zabbix side
 - AWS Lambda --> AWS CloudWatch --> metrics to this project --> Zabbix Proxy --> Zabbix Server --> Dashboard
    - Lambda sends metrics to CW in 1-minute intervals

Firehose Buffering:
 - Metric Sream --> Firehose Transform buffering --> Lambda --> Firehose buffering --> destination

# Config
 - Central config script:
    - two parts: `metrics_def.py` and running `prj_config.py`
    - metrics_def.py:
        - python script containig only a list of `LLDMultiTriggerMetricConfig` instances
        - list must be named `MetricConfigs`
        - create more instances based on the sample ones
        - **TRIGGER EXPRESSION CONSTANTS MUST BE ENCLOSED IN DOUBLE QUOTES**
            - i.e. `last({})>{}` **is not** correct, `last({})>"{}"` **is** correct
            - first `{}` references the item, second the constant
            - may be numbered as well for reverse order or multiple references:
                - `"{1}"<last({0})` = last value is greater than constant
                - `count({0},5m,"ge","{1}")>7 or avg({0},5m)>"{1}"` = number of function invocations with metric higher than constant was greater than 7 for the past 5 minutes or the average of metric value for the past 5 minutes is greater that the constant
        - The list serves as configuration of both Zabbix (discovery,items,triggers...) and AWS (what metrics to stream, how to transform to Zabbix items)
        - **crucial!!**
    - prj_config.py:
        - guided creation of config files and AWS SAM parameters JSON file
        - config files include configs for naming things: The `<suffix>` in naming conventions, Zabbix LLD Macro names and AWS Lambda Tag names
            - defaults are pre-defined and recommended
        - AWS SAM parameter JSON includes parameters and values to the SAM template, in JSON format -- used as input to `sam.py` script
            - defaults are pre-defined for some parameters
            - feel free to change the values
            - can leave out parameters without defaults -> you'll have to fill them in later
            - AWS Metrics to be streamed are extracted from `metrics_def.py MetricConfigs`
            - special statistics for metrics must be defined manually in `metric-stream.yaml` template (below)
        - each of these (config files / parameter JSON file) can be skipped by pressing CTRL+C and the files won't be created
        - also creates metric mapping (AWS Lambda metric + statistic -> Zabbix items) for `basic_handler` based on `MetricConfigs`
        - finally copies `metrics_def.py` to `scripts` directory for the `zapi` module to be able to create initialize Zabbix

 - AWS special config: 
    - zblamb-sam/
        - metric-stream.yaml
            - includes demo infrastructure, feel free to modify (remove EC2 instance...)
            - only Firehose transform Lambda, Firehose Data Stream and Meric Stream objects must remain
                - Transform Lambda must have ZBLAMB_PROXY_IP environment variable defined!
                - IP address of the Zabbix Server/Proxy it will be sending data to
                - if the Zabbix Server/Proxy is in a private subnet in AWS VPC, the transform lambda must be "inside" as well
            -  more statistics (see AWS::CloudWatch::MetricStream documentation) can be added manually to the Metric Stream
                - only for Metrics defined in `metrics_def.py`


# TODO
 - Resolve problems:
    - "Time consistency"
        - Parallel transform Lambda invocations -- allow or not?
            - disable by setting Lambda timeout <= Firehose Buffering -- may be triggered early by size buffering setting
        - out-of-order delivery on Zabbix
            - Lambda invocation 0 has connectivity problems
            - Lambda invocation 1 delivers metrics to Zabbix
            - invocation delivers metrics -- after invoc 1! 
            - Earlier metrics delivered later than current latest metrics
            - Clock param of Zabbix Trapper protocol?
            - solve by eliminating parallelism?
    
    - end with error in Transform lambda, if error in Zabbix **!!**
    - Documentation **!!**
    - controll packet size going to Zabbix
    - billing??

 - Benchmark the infrastructure:
    - 1000 active instances at once (at all times?)
    - Transform lambda duration, parallelism?
    - figure out good parameters -- Firehose buffering time and size, Lambda timeout, ...
    - mock Firehose? (Not to have actual 1000 lambda instances running at once all the time)
    - overload Trapper and Transform Lambda (how much required to overload) **!!**

 - Templates:
    - networking template -- VPC, Subnets
        - export VPC, subnet IDs
    - Zabbix template
        - Server: Public Subnet (or private with VPN)
        - Proxy: private subnet
        - possibly Agent: private
        - SSH keys, Security Groups
    - Metric Stream template
        - Metric Stream, Firehose, Transform Lambda (inside VPC)
        - Mock lambda? Or separate template?
    - use conditions:
        - `!If: [<param_x>_defined, !Ref <param_x>, !ImportValue ZBLamb::<param_x>]`
        - how to define condition `<param_x>_defined??`
        - zapi depends on whether proxy is created! propagate with prj_config
    - can SAM deploy template without building? (vanilla CF template)

 - Central config for AWS and Zabbix
    - more params in template: Lambda timeouts etc. in central config

 - create readable doc for the project

 - Setup Metric Stream
    - CloudWatch -> Firehose -> Transformation Lambda -> "S3" / any other destination
        - send 1 packet to Zabbix per 1 metric stream record (not all at once) -- for correct timestamps
        - periodically discover all Lambdas -- **TEST**
            - after a specific period, crawl through all Lambda functions and discover them
            - ZBX_LLD_KEEP_PERIOD=0, since re-discovers only existing functions and not deleted in AWS
            - in Transform lambda (`if should_rediscover(): rediscover()`) or new Lambda, invoked periodically
            - no need to worry about faulty deletions in Zabbix
            - deleted functions in AWS might pend in Zabbix for a long time (deleted in beggining of re-discovery period)
            - must ensure discovery of new functions
                - just a boolean ZabbixMonitored Lambda Tag?
                - discovering just this function would delete every other function (ZBX_LLD_KEEP_PERIOD=0)
                - must ensure all functions are re-discovered with new function
                - either postpone or skip sending metrics of new function until discovered in periodic process, or send discovery packet with every function once a new function is found
            - priority updates: just update the priority in AWS and wait until next discovery period

 - configure Zabbix
    - maybe change docker images to CentOS? Since the instances run on Amazon Linux, based off CentOS?

 - Change paths of IAM roles
 
 - move templates to SAM

 - create network stack:
    - VPC + IGW + NATGW
    - Public Subnet + Private Subnet + Routing tables for both
    - VPC endpoint (AWS PrivateLink) for Firehose

# Done
 - Naming Convention:
    - all 'names' (e.g. Zabbix item names, Zabbix host names or trigger names) must be same across Zabbix and AWS config!
        - set with central config script
        - main idea: the Zabbix host that manages its stuff has a 'simple' name or 'suffix', on which all other names are based
        - all zabbix names are lower-case, except for Lambda function name (anything outside of `[]` is lower-case)
        - LLD rule under the host has (item) name `discovery.<suffix>`
        - items have name `<zabbix_metric>.metrics.<suffix>[<function_name>]`
            - if one AWS metric has more statistics tracked by zabbix, the convention would be `<statistic>.<aws_metric>.metrics.<suffix>[<function_name>]`, e.g. `max.duration.metrics.multi-trigger-mapping-zblamb[{#FN_NAME}]` for item prototype
            - the real item name is defined while configuring the metric in `MetricConfigs` of `metrics_def.py`
        - triggers have name `<severity>.<zabbix_metric>.triggers.<suffix>[<function_name>]` 
        - proxy has name `proxy.<suffix>`
        - host group has name `group.<suffix>` 

 - Setup Metric Stream:
    - namespace: AWS/Lambda, metric: Errors, Duration
    - Firehose source = DirectPUT
    - CloudWatch sends accumulated metrics per 60 seconds
    - CloudWatch -> Firehose -> Transformation Lambda -> "S3" / any other destination
        - Transformation Lambda `basic_handler`:
            - can be in VPC with Zabbix Proxy/Server if the proxy/server is in a private subnet on EC2
            - takes data "to transform"
            - extracts ".values", ".timestamp" and ".dimensions.functionName" (from jsons with single dimension)
            - transforms extracted data to Zabbix Trapper packet based on configured metrics in `metrics_def.py`
            - sends extracted data to Zabbix Proxy/Server 
            - returns ``{"recordID": "provided ID by Firehose", "result": "Dropped", "data": ""}`` to Firehose
                - Firehorse does not pass it forward to the destination

 - Central cofiguration script
    - scripts config, template params
    - configure zapi mapping, transformation and metrics to stream using just single MetricConfig List
        - MetricConfig also includes name of AWS metric (and statistic) it maps to zabbix items
        - have python configuration file that would include just the MetricConfig List
        - propagate this List to zapi.py (config module), SAM template (metrics parameter) and Transform Lambda (metric mapping AWS->Zabbix)
            - Transform: from MetricConfigs, create JSON that maps AWS Metric + AWS statistic to Zabbix item name

 - configure Zabbix metrics
    - add host with name `<suffix>` (e.g. zblamb)
        - no interface
    - possible flows:
        - Single-Host Multi-Trigger Per-Lambda trapper items via Low-Level Discovery
            - Lambdas are tagged in AWS with a prioirty, e.g. `{PRIO=0}`
            - host + discovery rule with key e.g. `discovery.<suffix>`
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
                - for each metric, parametrized by function e.g. `error.metrics.<suffix>[${FN_NAME}]`/`min.duration.metrics.<suffix>[${FN_NAME}]`
            - trigger prototypes
                - create for each item and each Zabbix priority one trigger
                    - e.g. `INFO.error.metrics.<suffix>[${FN_NAME}]`/`AVERAGE.min.duration.metrics.<suffix>[${FN_NAME}]`
                - all triggers have same expression, just the constants differ
                    - `count(/<suffix>/errors.metrics.<suffix>[{#FN_NAME}],5m,"ge","{$ERROR_INFO:{#PRIO}}")>=1`    
                    - `count(/<suffix>/errors.metrics.<suffix>[{#FN_NAME}],5m,"ge","{$ERROR_HIGH:{#PRIO}}")>=1`
                - do not create triggers for left out entries in the configuration table
                    - using discovery rule Overrides
    - RE-discovery
        - When Zabbix recieves FN_NAME,PRIO where FN_NAME is already known and PRIO is changed (update function priority), it updates all items/triggers that are checked as "discover" in LLD rule / override
        - --> in multi-trigger mapping, changing the priority leaves triggers not to discover intact, WILL NOT DELETE THEM as is required
        - solution = scripts/lambda_update_priority.py script:
            - deletes Zabbix triggers for the funtion (contains `triggers.<suffix>[<FnName>]`),
            - updates the priority of a Lambda function, 
            - discovers it anew

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

# Abandoned Ideas
 - Setup Metric Stream:
    - CloudWatch -> Firehose -> S3 bucket -> Lambda -> Zabbix Protocol -> Zabbix Proxy/Server
        - Lambda:
            - downloads the metric JSON(s) file(s)
            - the rest is same as `basic_handler`, does not have to return anything
    - CloudWatch -> Firehose -> HTTPS Endpoint -> Zabbix protocol -> Zabbix Proxy
        - HTTPS Endpoint must have public IP address
        - HTTPS Endpoint does the same as `basic_handler`, just complies with the endopoint mechanism
        - Firehose cannot currently access instances in a private VPC subnet
            - https://docs.aws.amazon.com/firehose/latest/dev/controlling-access.html#using-iam-http
 
 - Setup Metric Stream
    - CloudWatch -> Firehose -> Transformation Lambda -> "S3" / any other destination
        - send 1 packet to Zabbix per 1 metric stream record (not all at once) -- for correct timestamps
        - do not discover already discovered Lambdas in Zabbix
            - "Cache" in Lambda tags:
                - ZabbixMonitored Tag: timestamp of time of discovery
                - Transform lambda config: after how long Zabbix deletes the discovered objects 
                - Transform lambda could (should) re-discover before Zabbix keep period expires
            - Zabbix discovered objects have state: discovered, no longer discovered
                - state changes to "discovered" when last discovery packet includes its LLD macros
                - state changes to "no longer discovered" when last discovery packet does not include its LLD macros
                - when new discovery packet arrives without its LLD macros in "no longer discovered" state and keep period expires, the object is deleted
            - optimal values:
                - ZBX_LLD_KEEP_PERIOD: 
                    1. find expected rate d (= 1/period) of least frequent Lambda Function
                    1. using exponential distribution with rate=d, find time interval T, in which it is highly probable that the least frequent function will get invoked
                        - e.g. 99.99 percentile = 9.210340/d = ~ 9 times the period
                        - 99.9 percentile = 6.907755/d = ~ 7 times the period
                        - p percentile = ln(1/(1-p))/d = ln(1/(1-p)) times the period
                    1. set ZBX_LLD_KEEP_PERIOD >= T
                        - very high probability that even the least frequent function is invoked prior to expiration in Zabbix
                - AWS re-discovery period for Lambda function F:
                    - for all functions, including the least frequent one
                    1. find expected rate Fd of function F
                    1. get time interval FT, in which F is very likely to get invoked (same percentile as with ZBX_LLD_KEEP_PERIOD)
                        - FT = ln(1/(1-p))/d, p is same as chosen in ZBX_LLD_KEEP_PERIOD, d is characteristic of F
                    1. set re-discovery period for F to ZBX_LLD_KEEP_PERIOD - FT
                        - => the least frequent function will have re-discovery period of 0 => re-discover each time
                        - not true if ZBX_LLD_KEEP_PERIOD > T
                - expiration of ZBX_LLD_KEEP_PERIOD in Zabbix is very likely for functions that do not exist anymore
                - assumption of exponential behavior! For better results, find conrete rate distribution of each function
                - ZBX_LLD_KEEP_PERIOD > T reduces communication, but deleted functions may pend longer in Zabbix
            - Configuration:
                - pick ZBX_LLD_KEEP_PERIOD > P*expected_max_period and set AWS re-descovery period to ZBX_LLD_KEEP_PERIOD/P
                    - probability of re-discovery of least frequent is 1-e^(1-P), assuming exponential behavior
                        - P=2 => 63.21 %, P=7 => 99.91 %
                    - all functions invoked more frequently than the least frequent one will be re-discovered unnecessarilly often, but it should be very unlikely that a function will get unintentionally deleted
                    - the higher P, the less likely are faulty deletions, but the higher is amount communication
                    - also the higher P, the longer it takes Zabbix to remove a function (they might pend for a long time)
                    - currently set to P=2 (ZBX_LLD_KEEP_PERIOD should be configured accordingly)

 - Configure Zabbix Metrics
    - possible flows:
        - aggregate functions
            - add trapper items to the host (`<suffix>=zblamb-lambda-errors`):
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
    - Lambda Metrics: https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics.html

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

 - Calling python modules
    - calling module already imported by parent: https://stackoverflow.com/questions/43393764/python-3-6-project-structure-leads-to-runtimewarning