# Zabbix Lambda monitoring project
A project that lets you stream Lambda function metrics from CloudWatch to external (on-premises) or internal (in EC2 instance) Zabbix installation. The project mainly contains an AWS SAM template to setup the streaming logic and a script to setup Zabbix. Then it also includes CloudFormation template to create a VPC with a public and private networkm a template to spin up Zabbix server, optionally with a Zabbix Proxy in EC2 instances and a few utility scripts to test out Zabbix.

## Set it up
To set the stream up, you'll have to configure this project first, then your Zabbix Server instance and lastly spin up the AWS resources.

### Project configuration
The project is configured in two steps. Firstly, the desired metrics (and statistics) must be set. Then, Configuration files must be generated using prj_config.py.

#### Metrics configuration
To understand the metrics configuration, one should understand how the transformation from Lambda priorities to Zabbix severities engineered in this project works. This is explained later on in this documentation, but a short recap:

Zabbix:
 - Zabbix defines a set of 'hosts' with a unique Zabbix host name. A 'host' can be monitored by the Server directly or via a Zabbix proxy.
 - Each 'host' has several 'items', an object that monitors a single metric of various data types known to Zabbix (unsigned,float,text,char,log).
 - 'items' themselves also have type, this project only uses the 'Zabbix trapper' type.
 - In 'hosts', there can be rules defined to automatically discover entities, this project uses such discovery rule. However it is not required the user knows how it works.
 - Apart from items, 'host' also has 'triggers', an object that sets off a problem / an event of a specific *severity* (Not Classified, Information, Warning, Average, High, Disaster) when the 'trigger's expression evaluates to true. The user is required to know how to write trigger expressions. Read Zabbix documentation of your Zabbix version. Note that expressions include a function, *host and item name* and a *constant* the output of the function is compared against.
 - For discovery rules, item and trigger prototypes are defined: stubs of items and triggers that will be filled in and created concretely for every discovered entity.

Lambda priority to Zabbix severities transformation:
 - This project defines a number of Lambda *priorities* (0-4), specified in the lambda's tags
 - Each Lambda priority is mapped to a subset of Zabbix severities, creating pairs (*priority*,*severity*)
    - so if priority 2 is mapped to {Warning,High}, the pairs are (2,Warning), (2,High)
 - each pair of the mapping is assigned a *constant* used in trigger expression
 - There is one such mapping (priority,severity) -> constant for **each** configured metric
    - note that metric has several meanings already: an AWS metric, a metric as an instance of LLDMultiTriggerMetricConfig class in configuration of this project, and a single measurable value. 

As for the configuration, metrics are instances of the class LLDMultiTriggerMetricConfig (in python), which are defined in a list MetricConfigs in the file (python script) metrics_def.py at the root of the project. There are some sample metric configs pre-defined as examples. The constructor of each instance needs the following:

 - zbx_name = name of the "metric" in Zabbix (will be expanded) and for the user to distinguish. Must only include characters allowed in Zabbix item names. The item name will be `<zbx_name>.metrics.<suffix>[<FunctionName>]`, suffix will be explained below and FunctionName is name of the Lambda Function, filled in automatically using Zabbix discovery.
 - zbx_value_type = data type of the item in zabbix. Allowed values are "int","float","text","log" and "char" ("int" is unsigned in zabbix)
 - aws_metric_name = name of the metric in AWS CloudWatch. See the monitored metrics of Lambda Functions by CloudWatch in AWS documentation. Interesting ones are 'Invocations', 'Errors' and 'Duration'. AWS CloudWatch accumulates metrics over 1 minute and provides aggregated values. Aggregated values are then buffered for a configured time period before ultimately sent to Zabbix.
 - aws_statistic_name = name of the statistic to take from the specified aws_metric_name. AWS provides several statistics (sum,min,max,count) for each accumulated metric you can choose from. You can also add more statistics, but has to be configured manually (explained later). For metrics Invocations and Errors, use the sum statistic (as per AWS documentation)
 - priority_mapping = mapping of Lambda priorities to Zabbix severities and constants. A table implemented with nested dictionaries. See below.
 - zbx_trigger_expression_pattern = pattern of the expression for each trigger prototype of the metric. A metric has as much trigger prototypes as priority/severity mapping pairs, each of these trigger prototypes has the same expression. They will differ slightly for each function (function name and priority will be filled in). On how to specify the expression pattern, see below.

The first four fields are self-explanatory, the last two need special care. The priority mapping is a dictionary, where keys are instances of the LambdaPriority class defined in the scripts.zapi python module. Not all priorities must be present in the dictionary, some may be left out. There can also be a special priority with the value -1, that will be used for any invalid or left out priority. The values of the keys (which are Lambda priorities) are nested dictionaries. These nested dictionaries have keys corresponding to Zabbix severities, represented by the ZabbixSeverity enum class defined in the scripts.zapi module. Severities may be left out as well. The values of these severities are the constants used in trigger expression. This may all seem confusing yet, but there will be examples ahead. Leaving a severity out for each Lambda priority results in not creating the trigger prototype with that severity. Triggers are also created dependent on each other, lower severity depends on higher (i.e. when trigger with higher severity is set off, lower severity triggers are not, thanks to which Zabbix dashboard is not spammed with multiple problems revolved around the same function -- only the highest severity problem is shown). You can also 'leave out' a severity by specifying the constant as python's `None`.

Zabbix trigger expression patterns are trigger expressions with left-out 'server' and constant, against which the result of function called on the 'server' is compared. The 'server' in Zabbix terms is unique identificator of an item and consists of Zabbix host name and the item name. Both the server and the constant will be inserted programatically. The user only has to specify where in the expression they should be filled in. The expression pattern is a string on which the python's `format` method will be called with server and constant as arguments, in this order. If in place of the server and constant is the `{}` string, they will be replaced in that order. A more fault-proof way would be to specify `{0}` in place of the server and `{1}` in place of the constant. This way, you can even have multiple functions and comparations in the expression. It is highly important that the constant term is surrounded by quotes (")! I.e. there are quotes around each `{1}` (or the second `{}`)

Examples:

In metrics_def.py, there are some pre-defined metric configs to use as examples. Feel free to copy from them.

Simply check the last value:

        LLDMultiTriggerMetricConfig(
            zbx_name="max.duration",
            zbx_value_type="float",
            zbx_trigger_expression_pattern='last({0})>="{1}"',
            aws_metric_name='Duration',
            aws_statistic_name='max',
            priority_mapping={
                LambdaPriority(0): { ZabbixSeverity.DISASTER: 1000.0 },
                LambdaPriority(1): { ZabbixSeverity.DISASTER: 1500.0,   ZabbixSeverity.HIGH: 750.0},    
                LambdaPriority(2): { ZabbixSeverity.HIGH: 1000.0, ZabbixSeverity.AVERAGE: 500.},        
            }
        )

This instance defines a 'max.duration' item in Zabbix, where values are real floating numbers. To this item, values form the AWS CloudWatch Duration metric's max statistic will be pushed -- i.e. the maximum duration of all accumulated lambda invocations. If a Lambda is invoked 3 times in a minute and operated for 250.0 ms the first time, 370.0 ms the second time and 240.0 ms the last time, the value 370.0 will be forwarded by AWS Metric Stream. The expression will evaluate to true when the last value (the last maximum duration) is higher than a constant specified in the priority_mapping table. In the table, only 3 priorities are defined. For functions with priority 0, a DISASTER trigger will fire, if the last maximum duration was 1 second or more (Duration is measured in miliseconds). For function with priority 1, HIGH trigger will fire, if at least one invocation of the function took 750 ms or more and DISASTER if it took 1500 ms or more. With functions of priority 2, AVERAGE will set off in case an invocation took half a second or more and HIGH trigger when it took a second or more. Other priorities, including undefined ones, will not fire any triggers. Note that for the Duration metric, the 'max' statistic tracks "if at last one function took more than X ms", whereas the 'min' statistic tracks "if all functions took more than X ms". Also Note that in this case, the expression could be `'last({})>="{}"'`, since item identification is first and constant is second, without additional references to the two.

Check number of metrics and their average:

        LLDMultiTriggerMetricConfig(
            zbx_name="count_avg.duration",
            zbx_value_type="float",
            zbx_trigger_expression_pattern='count({0},15m,"ge","{1}")>=7 or avg({0},15m)>"{1}"', 
            aws_metric_name="Duration",
            aws_statistic_name="min",

            priority_mapping={
                LambdaPriority(1):  { ZabbixSeverity.HIGH: 1500,  ZabbixSeverity.AVERAGE: 1000},    
                LambdaPriority(2):  { ZabbixSeverity.HIGH: None, ZabbixSeverity.AVERAGE: 1500},
                LambdaPriority(-1): { ZabbixSeverity.NOT_CLASSIFIED: 3000}     
            }
        )

Creates items with name 'count_avg.duration' of data type float, that will be fed with the minimum duration of CloudWatch accumulated metrics of the function. The expression triggers if for the last 15 minutes, at least 7 times all function invocations in a batch of accumulated invocations took more than constant or the average of minimum durations within the 15 minutes was greater than the constant. The constants depend on the priority_mapping table. Functions of priority 0,3,4 and all undefined priorities will fall under the third priority, -1. Priority 1 functions trigger HIGH if 7 or more batches took at least 1500 ms or the average was more than 1500 ms, and trigger AVERAGE if it was 1000 ms. Priority 2 functions only trigger AVERAGE (HIGH is set to None and other severities are left out) with the constant set to 1500 ms. Functions with any other priority trigger NOT_CLASSIFIED for the constant 3000 ms.

That's it for metrics definitions. You can define how many metrics you wish, but with more metrics, more computing on Zabbix is required. This was also the hardest thing to configure, so congrats. It should be chill from now on.

#### Configuration Files
After metrics are defined, configuration files must be generated. These are configuration files for Python scripts as well as Lambda functions created as part of this project and a JSON file containig parameters to CloudFormation/SAM templates. To generate these, run prj_config.py using `python3 prj_config.py`. The script will lead you through two sets of configs: python configs (for scripts and Lambdas) and SAM template parameters JSON. A description of the config value will be printed, then on next line the name of the config and default value inside parenthesis. You can then fill in your desired value and confirm with Enter, or just press Enter without inputting anything to submit the default value. Any set (python configs or SAM parameters) can be skipped with CTRL+C, but the first time you run this, you must submit all python config values (even if you wish to keep defaults only) to actually create the files. SAM parameters shouldn't be skipped as well, since it will make things easier a few steps ahead. The config can be changed anytime before setting up Zabbix and SAM. In case you wish to update the config after, see a following section on changing the config.

There are two python configs: 
 - ZBX_SUFFIX: this is a string that will be at the end of all zabbix created objects. Names in Zabbix are hierarchical and work like DNS domains - layers are separated by a comma and the root is this ZBX_SUFFIX config (unlike DNS, where root is .). See the naming convention section somewhere below
 - AWS_PRIO_TAG: name of the priority tag of Lambda functions that yield their priority that maps to Severities and constants.

SAM parameters are plenty. The script generates all possible SAM parameters, but only a subset of them may be required, based on your use case. There are 4 SAM templates and each uses a subset of parameters. If you only plan to set up the metric stream from AWS CloudWatch to Zabbix, most of them will be irrelevant. In the description of the currently submitted parameter, you can see which templates use the parametr. If not specified, only the metric-stream template uses that parameter.

The script also adds some configs that you were not prompted to fill in. You should leave these to their values, unless you feel confident with knowing their purpose.

### (Optional) Spin up Zabbix or whole Demo App
If you do not have your own Zabbix Server (and optionally Proxy), you can spin up an EC2 instance running Zabbix version 5.4 and optionally a Zabbix Proxy v. 5.4 using a CloudFormation template. Alternatively, you can spin up Zabbix and the "application" of this project in a single SAM template.

To just create Zabbix Server (and optionally Proxy), create a CloudFormation stack with the template located at `zblamb-sam/zbx_server_proxy.yaml`. Either upload it to to AWS and create it manually, use SAM cli as

        sam build -t zbx_server_proxy.yaml && sam deploy --guided

inside the zblamb-sam directory, or use the sam.py utility (**recommended**) as 

        python3 sam.py build -t zbx_server_proxy.yaml ./template_params.json && python3 sam.py deploy [--guided] ./template_params.json
        
from inside the zblamb-sam directory. The sam.py utility fills in the SAM parameters you submitted in project configuration (using prj_config.py) for you, so you don't have to fill them again. It also automatically fills some parameters you did not have to specify. Just use sam.py for building and deploying... (it wants to be noticed, sam.py). Whether to create Zabbix Proxy is set via the ZBLambCreateProxy parameter. If you do not have a configured VPC, you can set it up using the `zblamb-sam/networking.yaml` template (either of the 3 ways). The templates export some values that can be used in the main template, if not filled out in its parameters (e.g. leaving ZBLambZabbixIP empty uses the Server or Proxy IP exported from the zbx_server_proxy template).

Alternatively, you can spin up a whole demo application with optionally a new VPC with two subnets, Zabbix Server and optionally Proxy and the "application" of this project. All is defined in the `zblamb-sam/demo.yaml` template as nested stacks. You can choose not to create the VPC (in which case you need to provide it) or not to create the Proxy, same as above. To build the demo, from inside the zblamb-sam directory call 

        python3 sam.py build ./template_params.json && pyhon3 sam.py deploy [--guided] [--no-confirm-changeset] ./template_params.json

This sets the whole project up with demo metrics as well, not the metrics you may have defined yourself. To change the metrics, update the stack as described in one of the sections below. For the demo to work, you'll need to configure zabbix and start monitoring your Lambdas, as described in the next sections. The AWS application is set up in demo. Also, as this is just a demo app, many parameters are left to their defaults without inputting your submitted parameters. 

### Configure Zabbix
Now that the project is configured (and you have your Zabbix instance), you have to set up your Zabbix Server to accept metrics sent from CloudWatch. To do so, you'll need to call the scripts.zapi module. First, install dependencies by calling from the root directory:

        pip3 install -r scripts/zapi/requirements.txt

Then, if you only have Zabbix Server, from root directory run 

        python3 -m scripts.zapi <frontend_address> <frontend_port> server

where `<frontend_address>` and `<frontend_port>` are the IP address or DNS name and port the Zabbix frontend listens on (if created using zbx_server_proxy template, address is IP of the server and port is 80). This call creates a new host group in Zabbix, a new host in that group, assigns a Low-Level Discovery Rule to the host, adds item and trigger prototypes to it as well as some overrides, and creates user macros for the host. Zabbix is then ready to recieve discovery packets and item metrics of discovered functions.

If you run Zabbix Proxy and want to push AWS metrics through the Proxy, from root run:

        python3 -m scripts.zapi <frontend_address> <frontend_port> proxy <proxy_name>

where the first 2 arguments are same as above and the last argument is identificator of the Proxy. The proxy identificator can be name of an existing proxy in Zabbix (host name), DNS name or IP address. The script first checks whether in Zabbix, there exists a proxy with the name you fill in, and if not, it creates a new proxy record with that name as the address (be it DNS or IP) and port 10051 (proxies must listen on that port) as a *passive* proxy (cannot create active proxies), with host name `proxy.<ZBX_SUFFIX>`. Then, all above objects will be created in Zabbix and the host will be marked as monitored by the Proxy.

Now, Zabbix should be configured.

### Configure AWS application
Now it's time to setup the application that sends AWS metrics to Zabbix. The application consists of AWS Metric Stream, Kinesis Firehose, a "Transformation" Lambda function, a "Discovery" Lambda function and optionally a "Mock" Lambda function to test the functionality. The Transformation and Discovery Lambdas may "reside inside" a VPC, indicated by the ZBLambLambdasInVPC parameter. This may be useful, when Zabbix is run in an EC2 instance in the VPC. In case the Lambdas will be created inside a VPC, you must also specify the ID of the VPC and ID of a private subnet inside the VPC. The "private" subnet ID can however be public (assigning public IP address), and Zabbix Server or Proxy **must** be reachable from the subnet. 

To set the stream up, go to the zblamb-sam directory and use SAM CLI or the sam.py utility to build and deploy the metric-stream.yaml template. Recommended is again using the sam.py utility:

      python3 sam.py build ./template_params.json

to build and

      python3 sam.py deploy [--guided] [--no-confirm-changeset] ./template_params.json

to deploy. The `--guided` option walks you through last-time edits to the parameters and stack and the `--no-confirm-changeset` option confirms the changeset automatically without requiring input by the user.

After that, the Discovery Lambda will start getting invoked with the rate you configured and Transform Lambda will start sending configured metrics to Zabbix as the AWS metrics are fed to it via the Metric Stream and Kinesis Firehose. You can disable discoveries by going to the Discovery Lambda in AWS Console and disabling the automatically created EventBridge rule that invokes the function. To disable periodic sending of metrics, go to CloudWatch in AWS Console, then Metric Streams and stop the stream. The functions can still be ivoked manually e.g. with `sam remote invoke` (do not use sam.py for invocations). 

Note that as the Discovery Lambda gets invoked the first time, it sends metrics to CloudWatch, which then sends them to Transform Lambda. The Transform Lambda also generates metrics, which are fed to it at a later time. Thus, a loop is created! You could hypothetically stop it by excluding the Discovery and Transform Lambdas from sending metrics. How? I do not know. But at least if the loop stops, you know something went wrong!

### Monitoring a Lambda Function

The Discovery Lambda only discovers Lambda functions that have a "priority tag". The name of the tag can be configured; by default, it is "PRIO". Any function without this tag will not be discovered in Zabbix and its metrics will not be sent by the Transformation Lambda. To start monitoring a function, add the tag to it (or create a function with the tag) and set the value of the tag to the priority of that Lambda. In the next "discovery epoch", the function will be discovered and metrics will start to be sent. Until the discovery, the function is not monitored. So if you for example set the discovery rate to 60 minutes and you add the priority tag to a function one minute after Discovery Lambda was invoked, you'll have to wait 59 minutes untill Zabbix notices the function, or invoke the Discovery Lambda early by hand.

To stop monitoring a Lambda, delete the priority tag and again either wait untill the next "epoch" or invoke Discovery manually. To change the priority of the Lambda: well, you know it! (Change tag value and wait or manual invoke).

As one of the automatically filled configs that you should not change, there's "zabbix LLD keep period" set to zero. This means every monitored Lambda function must be discovered again in every single discovery packet. Items and triggers of functions not discovered inside a packet will be deleted, with all item history. Moral of the story: do not discover new functions yourself, use the Discovery Lambda.

## Naming convention
In Zabbix, objects are named "hierarchically" in a tree manner, with layers separated by commas and the root of the tree being the ZBX_SUFFIX config value. Zabbix host group is

## How it works

## Changing configuration and Adding metrics