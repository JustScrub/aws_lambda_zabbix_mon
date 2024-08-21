# Zabbix Lambda monitoring project
A project that lets you stream Lambda function metrics from CloudWatch to external (on-premises) or internal (in EC2 instance) Zabbix installation. The project mainly contains an AWS SAM template to setup the streaming logic and a script to setup Zabbix. Then it also includes CloudFormation template to create a VPC with a public and private network, a template to spin up Zabbix server, optionally with a Zabbix Proxy in EC2 instances and a few utility scripts to test out Zabbix.

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
 - Apart from items, 'host' also has 'triggers', an object that sets off a problem / an event of a specific *severity* (Not Classified, Information, Warning, Average, High, Disaster) when the 'trigger's expression evaluates to true. The user is required to know how to write trigger expressions. Read Zabbix documentation of your Zabbix version. Note that expressions include a function, *host and item name* as input to the function and a *constant* the output of the function is compared against.
 - For discovery rules, item and trigger prototypes are defined: stubs of items and triggers that will be filled in and created concretely for every discovered entity.

Lambda priority to Zabbix severities transformation:
 - This project defines a number of Lambda *priorities* (0-4), specified in the lambda's tags
 - Each Lambda priority is mapped to a subset of Zabbix severities, creating pairs (*priority*,*severity*)
    - so if priority 2 is mapped to {Warning,High}, the pairs are (2,Warning), (2,High)
 - each pair of the mapping is assigned a *constant* used in trigger expression
 - There is one such mapping (priority,severity) -> constant for **each** configured metric
    - note that metric has several meanings already: an AWS metric, a metric as a configuration primitive of this project, and a single measurable value. 
 - Plot twist: each Lambda does not have a single priority. There is one priority for each configured metric.
    - the rest is the same, though
    - how to set the priorities will be explained in one of the following sections

As for the configuration, metrics are instances of the class LLDMultiTriggerMetricConfig (in python), which are defined in a list MetricConfigs in the file (python script) metrics_def.py at the root of the project. There are some sample metric configs pre-defined as examples. Instances in the list server as central configuration of the "metrics" in Zabbix (items and triggers) and of AWS function stream the metrics to Zabbix (which AWS metrics and statistics to stream to which Zabbix items). The constructor of each instance needs the following:

 - name = name of the "metric" for the user to distinguish. Must only include characters allowed in Zabbix trigger names. Names across all instances must be unique!
 - zbx_value_type = data type of the item in zabbix. Allowed values are "int","float","text","log" and "char" ("int" is unsigned in zabbix)
 - aws_metric_name = name of the metric in AWS CloudWatch. See the monitored metrics of Lambda Functions by CloudWatch in AWS documentation. Interesting ones are 'Invocations', 'Errors' and 'Duration'. AWS CloudWatch accumulates metrics over 1 minute and provides aggregated values. Aggregated values are then buffered for a configured time period before ultimately sent to Zabbix. The metric name must be equal to the name in AWS, including character case!
 - aws_statistic_name = name of the statistic to take from the specified aws_metric_name. AWS provides several statistics (sum,min,max,count) for each accumulated metric you can choose from. You can also add more statistics, but has to be configured manually (explained later). For metrics Invocations and Errors, use the sum statistic (as per AWS documentation). The name must be same as in AWS, case-sensitive. Zabbix item keys are derived from these arguments as such: `<aws_statistic_name>.<aws_metric_name>.metrics.<suffix>[<FunctionName>]`, where the arguments are converted to lower case, `<suffix>` is configurable (the ZBX_SUFFIX config in the next section, also see Naming convention) and `<FunctionName>` will be automatically filled in during discovery.
 - priority_mapping = mapping of Lambda priorities to Zabbix severities and constants. A table implemented with nested dictionaries. See below.
 - zbx_trigger_expression_pattern = pattern of the expression for each trigger prototype of the metric's item prototype. There's one item prototype per class instance. An item prototype has a trigger for each severity except those severities, that aren't defined for any priority in the mapping. Each of these trigger prototypes has the same expression. They will differ slightly for each Lambda function once a Lambda is discovered (function name and priority will be filled in). On how to specify the expression pattern, see below.

The first four fields are explained enough, the last two need special care. The priority mapping is a dictionary, where keys are instances of the LambdaPriority class defined in the scripts.zapi python module. Not all priorities must be present in the dictionary, some may be left out. There can also be a special priority with the value -1, that will be used for any invalid or left out priority. The values of the keys (which are Lambda priorities) are nested dictionaries. These nested dictionaries have keys corresponding to Zabbix severities, represented by the ZabbixSeverity enum class defined in the scripts.zapi module. Severities may be left out as well. The values of these severities are the constants used in trigger expression. This may all seem confusing yet, but there will be examples ahead. Leaving a severity out for each Lambda priority results in not creating the trigger prototype with that severity. Triggers are also created dependent on each other, lower severity depends on higher (i.e. when trigger with higher severity is set off, lower severity triggers are not, thanks to which Zabbix dashboard is not spammed with multiple problems revolved around the same function -- only the highest severity problem is shown). You can also 'leave out' a severity by specifying the constant as python's `None`. Whey you leave out a priority, discovered functions of that priority will fall under the special priority -1. If even priority -1 is left out, only items of the discovered functions will be created from the item prototype, without any triggers. If you leave out a severity under a priority, the trigger of that severity will not be discovered for function with the priority. If you leave out a severity for every priority, the trigger prototype will not be created (because no function, no matter its priority, would discover it).

Zabbix trigger expression patterns are trigger expressions with left-out 'server' and constant, against which the result of function called on the 'server' is compared. The 'server' in Zabbix terms is unique identificator of an item and consists of Zabbix host name and the item name. Both the server and the constant will be inserted programatically. The user only has to specify where in the expression they should be filled in. The expression pattern is a string on which the python's `format` method will be called with server and constant as arguments, in this order. If in place of the server and constant is the `{}` string, they will be replaced in that order. A more fault-proof way would be to specify `{0}` in place of the server and `{1}` in place of the constant. This way, you can even have multiple functions and comparations in the expression. **It is highly important that the constant term is surrounded by quotes (")!** I.e. there are quotes around each `{1}` (or the second `{}`).

Examples:

In metrics_def.py, there are some pre-defined metric configs to use as examples. Feel free to copy from them.

Simply check the last value:

        LLDMultiTriggerMetricConfig(
            name="max.duration",
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

This instance defines a `max.duration.metrics.<suffix>[{#FN_NAME}]` item prototype (from the aws_metric_name and aws_statistic_name arguments) in Zabbix, where `<suffix>` will be set in the next configruation steps and `{#FN_NAME}` is a macro that will be expanded with a Lambda function name, once it is discovered. The values are real floating numbers. To this item (of discovered Lambdas), values form the AWS CloudWatch Duration metric's max statistic will be pushed -- i.e. the maximum duration of all accumulated lambda invocations. If a Lambda is invoked 3 times in a minute and operated for 250.0 ms the first time, 370.0 ms the second time and 240.0 ms the last time, the value 370.0 will be forwarded by AWS Metric Stream. The expression will evaluate to true when the last value (the last maximum duration) is higher than a constant specified in the priority_mapping table. In the table, only 3 priorities are defined. For functions with priority 0, a DISASTER trigger will fire, if the last maximum duration was 1 second or more (Duration is measured in miliseconds). For functions with priority 1, HIGH trigger will fire, if at least one invocation of the function took 750 ms or more and DISASTER if it took 1500 ms or more. With functions of priority 2, AVERAGE will set off in case an invocation took half a second or more and HIGH trigger when it took a second or more. Other priorities, including undefined ones, will not fire any triggers, because the key `LambdaPriority(-1)` is left out. Note that for the Duration metric, the 'max' statistic tracks "if at least one function took more than X ms", whereas the 'min' statistic tracks "if all functions took more than X ms". Also Note that in this case, the expression could be `'last({})>="{}"'`, since item identification is first and constant is second, without additional references to the two. In Zabbix, one item prototype will be created along with three trigger prototypes: of the severities Disaster, High and Average, other severities are left out for all priorities. On discovery of function with priority 0, only the Disaster trigger will be discovered and the rest two won't.

Check number of metrics and their average:

        LLDMultiTriggerMetricConfig(
            name="count_avg.duration",
            zbx_value_type="float",
            zbx_trigger_expression_pattern='count({0},15m,"ge","{1}")>=7 or avg({0},15m)>"{1}"', 
            aws_metric_name="Duration",
            aws_statistic_name="max",

            priority_mapping={
                LambdaPriority(1):  { ZabbixSeverity.HIGH: 1500,  ZabbixSeverity.AVERAGE: 1000},    
                LambdaPriority(2):  { ZabbixSeverity.HIGH: None, ZabbixSeverity.AVERAGE: 1500},
                LambdaPriority(-1): { ZabbixSeverity.NOT_CLASSIFIED: 3000}     
            }
        )

Item prototype `max.duration.metrics.<suffix>[{#FN_NAME}]` is created, if it doesn't exist yet. The data type is real number, the concrete items of the prototype will be fed with the maximum duration of CloudWatch accumulated metrics of the function. The expression triggers if for the last 15 minutes, at least 7 times the slowest function invocation in a batch of accumulated invocations took more than constant or the average of maximum durations within the 15 minutes was greater than the constant. The constants depend on the priority_mapping table. Functions of priority 0,3,4 and all undefined priorities will fall under the third priority, -1. Priority 1 functions trigger HIGH if 7 or more batches had a function that took at least 1500 ms or the average was more than 1500 ms, and trigger AVERAGE if it was 1000 ms. Priority 2 functions only trigger AVERAGE (HIGH is set to None and other severities are left out) with the constant set to 1500 ms. Functions with any other priority trigger NOT_CLASSIFIED for the constant 3000 ms.

Multiple metrics and Lambda priorities:

        LLDMultiTriggerMetricConfig(
            name="max.duration",
            zbx_value_type="float",
            zbx_trigger_expression_pattern='last({0})>="{1}"',
            aws_metric_name='Duration',
            aws_statistic_name='max',
            priority_mapping={
                LambdaPriority(0): { ZabbixSeverity.DISASTER:  1000.0,   ZabbixSeverity.HIGH:  750.0 }, # fast functions
                LambdaPriority(1): { ZabbixSeverity.DISASTER:  5000.0,   ZabbixSeverity.HIGH: 3000.0 }, # slower functions
                LambdaPriority(2): { ZabbixSeverity.DISASTER: 10000.0,   ZabbixSeverity.HIGH: 7000.0 }, # slow functions
            }
        ),
        LLDMultiTriggerMetricConfig(
            name="errors",
            zbx_value_type="int",
            zbx_trigger_expression_pattern='count({},5m,"ge","{}")>="1"',
            aws_metric_name='Errors',
            aws_statistic_name='sum',
            priority_mapping={
                LambdaPriority(0): { ZabbixSeverity.DISASTER: 1                             }, # critical functions
                LambdaPriority(1): { ZabbixSeverity.DISASTER: 2,   ZabbixSeverity.HIGH:    1}, # less critical
                LambdaPriority(2): { ZabbixSeverity.HIGH:     2,   ZabbixSeverity.AVERAGE: 1}, # less severe
                LambdaPriority(-1): {severity: None for severity in list(ZabbixSeverity)}      # all other aren't critical
            }
        )

This example shows the reason behind multiple priorities for a Lambda function. With both of these metrics defined, a discovered Lambda creates Zabbix items for both the metrics: `max.duration.metrics.<suffix>[<FnName>]` and `sum.errors.metrics.<suffix>[<FnName>]` (these are created from the appropriate item prototypes). Here, the priorities can be understood as some kind of classifications. The first metric, max.duration, classifies the function (based on its priority for this metric) accoriding to its expected duration. Functions that are expected to run for less than 750 ms should have the priority 0, functions that run for up to 3 seconds should have priority 1, priority 2 is meant for functions that take up to 7 seconds to run. Slower functions are not classified. The second metric, errors, classifies the functions based on their criticality: priority 0 is reserved for very critical functions, that trigger a disaster event in Zabbix with only a single error, priority 1 triggers high on one error and disaster on two errors, priority 2 is similiar to priority 1, except the severities are lowered. All other priorities do not set triggers off. Now, if a function had a single priority, say 0, that would mean it both has to be fast and critical. It would be impossible to have slow, yet critical function, or a fast function with lower severity. Having two priorities, one for each metric, enables the user to prioritize the function for each metric differently. This also allows for some "hacks" like extending number of priorities: make two metrics from the same AWS Metric/statistic value, with the same expression and make the mappings logically follow. Another "hack" could be the same metric value, expression and mapping, but the severities in the mapping lowered, thus allowing, for example, for higher severity duration (same as max.duration in this example) and lower severity duration (same as max.duration, but severities lowered to e.g. HIGH and AVERAGE). To follow the naming convention, one could name them as higher.max.duration and lower.max.duration.

That's it for metrics definitions. You can define how many metrics you wish, but with more metrics, more computing on Zabbix and in AWS is required. This was also the hardest thing to configure, so congrats. It should be chill from now on.

#### Configuration Files
After metrics are defined, configuration files must be generated. These are configuration files for Python scripts as well as Lambda functions created as part of this project and a JSON file containig parameters to CloudFormation/SAM templates. To generate these, run prj_config.py using `python3 prj_config.py`. The script will lead you through two sets of configs: python configs (for scripts and Lambdas) and SAM template parameters JSON. A description of the config value will be printed, then on next line the name of the config and default value inside parenthesis. You can then fill in your desired value and confirm with Enter, or just press Enter without inputting anything to submit the default value. Any set (python configs or SAM parameters) can be skipped with CTRL+C, but the first time you run this, you must submit all python config values (even if you wish to keep defaults only) to actually create the files. SAM parameters shouldn't be skipped as well, since it will make things easier a few steps ahead. The config can be changed anytime before setting up Zabbix and SAM. In case you wish to update the config after, see a following section on changing the config.

There are two python configs: 
 - ZBX_SUFFIX: this is a string that will be at the end of all zabbix created objects. Names in Zabbix are hierarchical and work like DNS domains - layers are separated by a comma and the root is this ZBX_SUFFIX config (unlike DNS, where root is .). See the naming convention section somewhere below
 - AWS_PRIO_VAR: name of the priority environment variable of Lambda functions that yields their priorities that maps to Severities and constants.

SAM parameters are plenty. The script generates all possible SAM parameters, but only a subset of them may be required, based on your use case. There are 4 SAM templates and each uses a subset of parameters. If you only plan to set up the metric stream from AWS CloudWatch to Zabbix, most of them will be irrelevant. In the description of the currently submitted parameter, you can see which templates use the parametr. If not specified, only the metric-stream template uses that parameter.

The script also adds some configs that you were not prompted to fill in. You should leave these to their values, unless you feel overly confident with knowing their purpose.

### (Optional) Spin up Zabbix or whole Demo App
If you do not have your own Zabbix Server (and optionally Proxy), you can spin up an EC2 instance running Zabbix version 5.4 and optionally a Zabbix Proxy v. 5.4 using a CloudFormation template. Alternatively, you can spin up Zabbix and the "application" of this project in a single SAM template.

To just create Zabbix Server (and optionally Proxy), create a CloudFormation stack with the template located at `zblamb-sam/zbx_server_proxy.yaml`. Either upload it to to AWS and create it manually, use SAM cli as

        sam build -t zbx_server_proxy.yaml && sam deploy --guided

inside the zblamb-sam directory, or use the sam.py utility (**recommended**) as 

        python3 sam.py build -t zbx_server_proxy.yaml ./template_params.json && python3 sam.py deploy [--guided] ./template_params.json
        
from inside the zblamb-sam directory. The sam.py utility fills in the SAM parameters you submitted in project configuration (using prj_config.py) for you, so you don't have to fill them again. It also automatically fills some parameters you did not have to specify. Just use sam.py for building and deploying... (it wants to be noticed, sam.py). Whether to create Zabbix Proxy is set via the ZBLambCreateProxy parameter. If you do not have a configured VPC, you can set it up using the `zblamb-sam/networking.yaml` template (either of the 3 ways). The templates export some values that can be used in the main template, if not filled out in its parameters (e.g. leaving ZBLambZabbixIP empty uses the Server or Proxy IP exported from the zbx_server_proxy template).

Alternatively, you can spin up a whole demo application with optionally a new VPC with two subnets, Zabbix Server and optionally Proxy and the "application" of this project. All is defined in the `zblamb-sam/demo.yaml` template as nested stacks. You can choose not to create the VPC (in which case you need to provide it) or not to create the Proxy, same as above. To build the demo, from inside the zblamb-sam directory call 

        python3 sam.py build -t demo.yaml ./template_params.json && pyhon3 sam.py deploy [--guided] ./template_params.json

This sets the whole project up. For the demo to work, you'll need to configure zabbix and start monitoring your Lambdas, as described in the next sections. After configuring Zabbix (via scripts.zapi module), you might need to restart the instances and possibly the Metric Stream and default Event Bus' scheduler rule (under EventBridge) driving the Transform and Discovery lambdas, respectively. Also, as this is just a demo app, many parameters are left to their defaults without inputting your submitted parameters. 

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

By default, the Transformation nor the Discovery Lambda have the priorities defined and so will not be monitored in Zabbix. To start monitoring them, set their priorities according to the next section.

### Monitoring a Lambda Function

The Discovery Lambda only discovers Lambda functions that have a "priority" environment variable. The name of the variable can be configured; by default, it is "ZBLAMB_PRIO". Any function without this env var will not be discovered in Zabbix and its metrics will not be sent by the Transformation Lambda. To start monitoring a function, add the variable to it (or create a function with the variable) and set the value of the variable to a string that contains space-delimited `<metric_name>:<priority>` pairs. The metric names refer to the name argument of configured metrics. For the third example from the Metrics configuration section, the priority value could be `"errors:1 max.duration:0"` (less critical, fast function). Some metrics can be omitted from the list of pairs. For all left out metrics, the triggers won't be created. For the same example, there may be a function with the environment variable set to `"max.duration:2"` (slow, not fault-critical at all). Leaving the variable value empty (empty string) or specifying priority for a metric two or more times is undefined behavior and you are free to watch the system fail multiple ways.

In the next "discovery epoch", the function will be discovered and metrics will start to be sent. Until the discovery, the function is not monitored. So if you for example set the discovery rate to 60 minutes and you add the priority variable to a function one minute after Discovery Lambda was invoked, you'll have to wait 59 minutes untill Zabbix notices the function, or invoke the Discovery Lambda early by hand.

To stop monitoring a Lambda, delete the priority variable and again either wait until the next "epoch" or invoke Discovery manually. To change the priority of the Lambda: well, you know it! (Change variable value and wait or manual invoke).

As one of the automatically filled configs that you should not change, there's "zabbix LLD keep period" set to zero. This means every monitored Lambda function must be discovered again in every single discovery packet. Items and triggers of functions not discovered inside a packet will be deleted, with all item history. Moral of the story: do not discover new functions yourself, use the Discovery Lambda.

## Naming convention
In Zabbix, this project names objects "hierarchically" in a tree manner, with layers separated by commas and the root of the tree being the ZBX_SUFFIX config value. Zabbix host group, to which the host belongs, is called `group.<suffix>`, the host is the top-level object named just `<suffix>`, its LLD rule `discovery.<suffix>`. The item prototypes of each metric are named `<aws_statistic_name>.<aws_metric_name>.metrics.<suffix>[{#FN_NAME}]`, where `<aws_statistic_name>` and `<aws_metric_name>` are the arguments to LLDMultiTriggerMetricConfig constructor of the same name when configuring metrics, converted to lower-case, and `{#FN_NAME}` is a LLD macro used in Zabbix, that will expand to the function name once it's discovered. The concrete item is thus "parametrized", as per Zabbix documentation, with the function name. This might seem to break the convention, but Zabbix's method of item parametrization is utilized. The name of the item is the "tree path" `<aws_statistic_name>.<aws_metric_name>.metrics.<suffix>`, conforming to the convention, and is parametrized by the function name, which in Zabbix is noted by appending with `[<FunctionName>]`. The trigger prototypes are named `<severity>.<name>.triggers.<suffix>[{#FN_NAME}]` with `<severity>` beign the name of Zabbix severity in upper case, as up to six triggers (one for each Zabbix severity) are created for each configured metric and `<name>` beign the name argument to configuration constructor. The same parametrization scheme as in items is utilized (although Zabbix does not mention parametrization of triggers, but it is at least consistent with item names). If you've created Zabbix Proxy using the zbx_server_proxy template, the proxy's Zabbix host name is `proxy.<suffix>`.

If you wish to continue this convention in your environment, you may name your metrics in a similiar manner. For example, if you create more metrics from AWS Duration metric, you may use a pattern like `<concrete_metric>.duration` for the name argument to the LLDMultiTriggerMetricConfig constructor. The sample metrics in metrics_def.py that come with the repository utilize this (in the count_avg.duration metric config).

## How it works
The project comprises of two components: Zabbix setup and AWS infrastructure. In Zabbix, multiple features are utilized and objects are setup using a python module in this repo, with path `scripts.zapi`. Note that this project was written for **Zabbix version 5.4**, some things may be different in other versions. In AWS, the main components are the Transformation Lambda and the Discovery Lambda. The former gets called with a batch of AWS metrics and their statistics and it transforms these to a packet Zabbix understands, with the correct host and item filled in, and sends the packet, delivering the configured AWS metrics to configured Zabbix items. The Transformation Lambda is fed by an AWS Metric Stream through an AWS Kinesis Firehose Datastreaming service. The concrete logistics will be discussed later. 

The Discovery Lambda gets called in configured intervals using AWS Event Bridge wihtout any arguments and the Lambda Function lists all Lambdas in your account and region, filters out Lambda functions without the priority environment variable, then to the remaining found Lambdas adds another environment variable, flagging the function as discovered, and discovers these functions in Zabbix. All functions are discovered, even those with the Zabbix discovered flag env var. This is a specification of Zabbix and discovery is intended to work like that. The Transformation Lambda too filters functions without the priority flag and functinons without the Zabbix discovered flag (because it does not exist in Zabbix yet).

### Zabbix side
On the Zabbix side, the main component is the Zabbix host named `<suffix>` (configured with ZBX_SUFFIX config). As hosts in Zabbix must belong to a group, a host group `group.<suffix>` is created. The host is created with a single "LLD rule" `discovery.<suffix>`, a quasi-item that accepts data in the JSON format containing a list of object, each object includes parameters named the same as "LLD macros", and their values are the values of these macros. The LLD rule can be of various types like any other Zabbix item, but in this project, only Zabbix Trapper is utilized. For clearer information, consult [Zabbix 5.4 Documentation](https://www.zabbix.com/documentation/5.4/en/manual/discovery/low_level_discovery). For this project, the macros are `{#FN_NAME}` and `{#<NAME>_PRIO}` (`<NAME>` is name of metric from metric configs, in upper case) that expand to the discovered Lambda Function name, resp. its priorities. 

AWS Discovery Lambda is expected to send the JSON list containig objects with these macros (not all priority macros are required), and the rest is handeled by Zabbix. LLD rules in Zabbix have their item and trigger prototypes (and might have host and graph prototypes, not used in this project). The prototypes are much like normal items and triggers, but the name and trigger expression are parametrized with LLD macros. Once a fucntion is discovered, i.e. the LLD rule accepts a valid JSON list with LLD macros, Zabbix creates items and triggers based on the prototypes, but with the LLD macros in their prototypes substituted with the values from the JSON list. For macros that are not present, the object are still created, but without the macro expanded (it is literally kept). These can however be deleted using 'Overrides', explained below, so that only relevant items and triggers remain for the discovered function.

Example: if the user configures the metrics exactly like in the third example in Metrics configuration examples (errors and max.duration metrics) with `<suffix>=lambda`, Zabbix configuration script creates item prototypes `sum.errors.metrics.lambda[{#FN_NAME}]` and `max.duration.metrics.lambda[{#FN_NAME}]` and trigger prototypes with expressions `count(lambda/sum.errors.metrics.lambda[{#FN_Name}],5m,"ge","ERRORS_<SEVERITY>:\"{#ERRORS_PRIO}\"")>="1"` (for each severity under errors metric triggers) and `last(lambda/max.duration.metrics.lambda[{#FN_NAME}])>"MAX.DURATION_<SEVERITY>:\"{#MAX.DURATION_PRIO}\""` (for each severity for max.duration metric). There will be two item prototypes (for Errors/sum and Duration/max AWS values) and five trigger prototypes (DISASTER and HIGH for max.duration; DISASTER, HIGH and AVERAGE for errors). Once the LLD rule `discover.lambda` recieves the following packet:

        [ 
            { "{#FN_NAME}": "my_lambda",       "{#ERRORS_PRIO}": "2"                              }, 
            { "{#FN_NAME}": "my_other_lambda", "{#ERRORS_PRIO}": "1", "{#MAX.DURATION_PRIO}": "0" } 
        ]

these items will be discovered and created:
 - `sum.errors.metrics.lambda[my_lambda]`
 - `max.duration.metrics.lambda[my_lambda]`
 - `sum.errors.metrics.lambda[my_other_lambda]` 
 - `max.duration.metrics.lambda[my_other_lambda]`

and also triggers with expressions:
 - `count(lambda/sum.errors.metrics.lambda[my_lambda],5m,"ge","ERRORS_<SEVERITY>:\"2\"")>="1"` 
   - for HIGH and AVERAGE severities = 2 triggers
 - `count(lambda/sum.errors.metrics.lambda[my_other_lambda],5m,"ge","ERRORS_<SEVERITY>:\"1\"")>="1"` 
   - for DISASTER and HIGH severities = 2 triggers
 - `last(lambda/max.duration.metrics.lambda[my_other_lambda])>"MAX.DURATION_<SEVERITY>:\"0\""` 
   - for DISASTER and HIGH severities = 2 triggers

Another important parameter of LLD rules is the keep lost resources period. Zabbix mentality is that every subsequent discovery packet should contain all previously discovered entities, not only newly discovered. If an entity that was previously discovered is not included in the next discovery packet (i.e. JSON object with its LLD macros is not present in the packet), Zabbix marks the objects of that entity (items and triggers) as "no longer discovered" and starts a counter for the objects set to the keep lost resources period. If the LLD macros do not show up in one of the subsequent packets recieved prior to the counter's deadline, the objects are deleted from Zabbix once a packet arrives after the deadline that does not contain the LLD macros as well. 

Since the Discovery Lambda lists all existing Lambda functions in an account with the priority env var and sends all of them in the discovery packet, the keep period is set to 0, meaning the Zabbix objects are deleted immidiately when a function is not re-discovered. This allows for easy Lambda deletion and priority updates. Deleting a function in AWS results in not sending it in the next packet, which removes the function altogether from Zabbix. Updating the priority var value deletes all objects with the old priorities and sets up new objects for the new ones: and as item prototypes only include the function name, the items and their data history are preserved and only triggers are re-created for the right metrics, with the right priority. Deleting the priority variable "unsubscribes" the function from being monitored by Zabbix.

Apart from just discovering items and triggers, LLD rules can have "Overrides". These are rules that modify the objects to be created prior to their creation, allowing for more configurability. Overrides have a filter, which is a condition on the accepted LLD macros, e.g. in the form '{#ERRORS_PRIO} is equal to "3"', name of the object to modify and rules on how to modify the object. One of the modifications is whether to discover the object, thus allowing not to discover (or create) triggers that are not required in the context of incomming priority, based on the metric configuration. For example, with the priority mapping

        priority_mapping={
            LambdaPriority(0): { ZabbixSeverity.DISASTER: 0 },
            LambdaPriority(1): { ZabbixSeverity.DISASTER: 1,   ZabbixSeverity.HIGH: 0},    
            LambdaPriority(2): { ZabbixSeverity.HIGH: 2, ZabbixSeverity.AVERAGE: 0},        
        }

trigger prototypes are created with the Disaster, High and Average severities. These must be created, because the priorities of all functions are not known apriory, but only after the discovery, so they "must be prepared". Other severity triggers however will never be needed for this metric, it is left out across all specified priorities, so there is no need to create prototypes of these severities. Then, after the arrival of discovery packet with a function of priority 0 (for the metric), the triggers of High and Average severity are not required according to the mapping, so they can be left out of discovery. This is the exact use case of Overrides in this project. 

Each metric and priority needs an Override rule, so there will be 6 Override rules per metric (priorities 0-4 + unclassified). The filter of each rule asserts that the metric-specific LLD macro was provided in the incommig packet and that the macro matches the rule's priority. For unclassified priorities, the rule asserts that the macro either is not provided, or does not match any of the priorities. If the filter passes, triggers for left out severities are marked as not to discover. If the the filter does not pass, the change is not applied. Upon recieving a packet with JSON objects, Zabbix for each object traverses all the rules there are, applying only those, for which the rule passes. From the batch of Override rules belonging to a single metric, exactly one rule is applied. The "effectivity" of rules is thus 1/6 (one in six rules gets to be run), but all must be present.

The last utilized feature of Zabbix is "User macros" and "User macros with context". Apart from LLD macros that are recieved in discovery packets, User macros are names of constants, defined in Zabbix globally or under a specific Zabbix host. User macros may be used in several places in Zabbix, this project uses these in trigger expressions. User macros can also have a "context", which is notated by appending colon (:) and context string (optionally enclosed in double quotes) to the name of the macro. Thus, there may be several variations of the User macro. When Zabbix observes a context with a User macro, it tries to match it to a defined User macro with context. If no match is found, the macro is expanded with the value of the basic User macro, without context. For example, there may be defined the macro `ERRORS` with value '42' and a macro with context `ERRORS:"1"` with value '14'. If Zabbix sees, e.g. in trigger expression, the macro `ERRORS:"1"`, it is expanded as expected to '14', however if in the expression, the macro would be `ERRORS:"not-defined"`, the value '42' would be substituted, since the `"not-defined"` context is not defined for the `ERRORS` macro. 

The catch with User macros with context is that the context can be passed from an LLD macro! Thus having defined the following (note the correlation with the above priority mapping example):
 - `ERRORS_DISASTER` = 16777216
 - `ERRORS_DISASTER:"0"` = 0
 - `ERRORS_DISASTER:"1"` = 1
 - `ERRORS_HIGH` = 16777216
 - `ERRORS_HIGH:"1"` = 0
 - `ERRORS_HIGH:"2"` = 2
 - `ERRORS_AVERAGE` = 16777216
 - `ERRORS_AVERAGE:"1"` = 0

we could write the Disaster trigger prototype expression as `last(lambda/sum.errors.metrics.lambda[{#FN_NAME}]) > "ERRORS_DISASTER:\"{#ERRORS_PRIO}\""` and the High and Average trigger prototypes accordingly. Then upon recieving a discovery packet with errors metric priority, the constant in the expression (the right-hand side) is expanded by Zabbix, according to the priority mapping. Discovering a function therefore automatically fills in the right constant, as configured in the mapping. See [Zabbix Documentaton](https://www.zabbix.com/documentation/5.4/en/manual/config/macros/user_macros_context) on User macros with context.

Just a quick note on quoting and context-less macros. For some reason, in order to work, both the macro and its context must be quoted. Since the context is a part of the macro name, the quotes around the context must be escaped. Without quotes, Zabbix fails to correctly expand the LLD macro upon discovery, the reason is not known. The context-less macros serve for the special priority -1 in mapping: if an undefined priority is discovered, the context name containing the undefined priority is not found and the default macro is expanded, just like the `ERRORS:"not-defined"` example. Default macros should be defined even if undefined priorities have no triggers (-1 priority left out in mapping, or all severities have a value of `None`) to make Zabbix happy. In this case, the default macro values are set to very high numbers, so that is is very improbable for any mal-discovered trigger to set off.

The Zabbix configuration script relies on the mentioned features – LLD rule, item and trigger prototypes, Overrides, User macros (with context) – to make purely Zabbix handle the whole discovery and taking care of accepted metrics. When rightly configured, Zabbix only needs to recieve discovery packets to the LLD rule quasi-item and metric packets to corresponding items, once they are discovered. Sending of these packets is handeled by the AWS side of the project.

#### Using Zabbix Proxy
When using Zabbix Proxy, there are more actors in the play. The communication between AWS side and Zabbix Server is not direct, AWS sends data to the Proxy, that depending on its configuration either sends the data to the server (active proxy), or waits for the server to ask for the data (passive proxy). This might seem as worthless information until you find out nothing works, you tear your hair because it does not make any sense and then finally it starts working, without you knowing the reason behind it all, becuse you just sat there in complete desperation and misery. 

The internals of communication between the Proxy and the Server have not been thoroughly studied, but from the harsh experience, here are some tips. Server and Proxy exchange more kinds of information, among which, there are 'Data' and 'Configuration'. The 'Data' are all metrics and values of items of the host monitored by the proxy, all numbers pushed to the Proxy by AWS side, in our case. The 'Configuration' is information about the items and everything the monitored host has. How I understand it works:
 1. during discovery, Discovery Lambda in AWS sends the filled LLD macros to Proxy's host
 1. Server asks Proxy for Data (passive proxy) or Proxy sends the Data to Server (active proxy)
 1. Server discovers items and triggers (but does not show them in frontend yet)
 1. Server sends Configuration, aka the discovered entities, to Proxy (passive) or Proxy asks for the Configuration (active)
    - and also shows them in frontend
 1. Everything is consistent now

The problem with this is the frequencies at which Data and Configuration are sent. Both can be configured. For passive proxies, these are configured at the Server with the 'ProxyConfigFrequency' and 'ProxyDataFrequency' configs in zabbix_server.conf. The former states how often Server sends configurations to its passive proxies and the latter how often it asks for data. Both are in seconds and the default for Data frequency is 1 second and for Configuration frequency, it is 1 *hour*. Who the hell came up with this? In the example, that means the discovered items and triggers are available after an *hour*. In the meantime, since the Proxy does not know about the item yet, it complains that they do not exist and Transformation Lambda fails due to this. It took me several days to figure this out. Sigh.

Since a Zabbix version newer than 5.4, Configuration frequency is set to 10 seconds by default. Since which one, I do not know.

For active proxies, the the frequencies are configured in their zabbix_proxy.conf as 'ConfigFrequency' and 'DataSenderFrequency'. Active proxies send data and ask for configuration (the opposite to passive proxies, where the server sends config and asks for data). Both are in seconds and the defaults are the same as for passive proxies. Since version 6.4.0 (as per [Zabbix Proxy docker page](https://hub.docker.com/r/zabbix/zabbix-proxy-sqlite3)), the 'ConfigFrequency' config is deprecated and the new one is 'ProxyConfigFrequency', same as the server's config, with the same new default set to 10 seconds. Data frequency is still configured with 'DataSenderFrequency'.

The thing to take from this section: **SET ProxyConfigFrequency OR ConfigFrequency TO LOWER VALUES!**. 

When **using docker**: these configs can be set via environment variables, but if having troubles with that, you'll have to change these configs manually inside the container. Bash into your container and echo-append the value to the config file residing in /etc/zabbix/:

      echo "ProxyConfigFrequency=<value>" >> /etc/zabbix/zabbix_server.conf
      echo "ConfigFrequency=<value>" >> /etc/zabbix/zabbix_proxy.conf

The first command should work, the second one has not been tested, so it might not be the case. Other than that, just change `<value>` to your number of seconds. Alternatively, you can copy the config file out of the container, edit it in e.g. vim and copy it back:

        docker cp <container_id>:/etc/zabbix/zabbix_<server|proxy>.conf $HOME
        vim $HOME/zabbix_<server|proxy>.conf
        (do your edits, exit vim)
        docker cp $HOME/zabbix_<server|proxy>.conf <container_id>:/etc/zabbix/zabbix_<server|proxy>.conf

Recommended would be something bellow the Transformation Lambda buffering time, as configured in SAM parameters (ZBLambTransformBufferingSeconds).

FEEL MY PAIN!!!!

Note: when trying to recreate on purpose, this acts weird. Using environment variable for some reason worked, but it seemed that setting ProxyConfigFrequency actually configured Data frequency, and incorrectly: when ProxyConfigFrequency set to 3600s, objects in Zabbix were discovered, whereas item data were not delivered. After setting to 30s, objects were immidiatelly visible and data was immidiatelly delivered. 

#### Zabbix configuration script flow
Now that the used features are described, let's have a look how the configuration script operates.

The script is called as a python module, scripts.zapi, that includes the script `__main__.py` that gets invoked. The script requires three or four arguments, depending on your Zabbix infrastructure. If you intend to push metrics to Zabbix Server directly, the script is called with three arguments, IP address or DNS name and port of Zabbix Frontend (running the API, which the script uses) and the argument "server". If metrics should be pushed via a Proxy, there are four agruments, the first two remain the same and the other two are "proxy" and a technical name of an existing proxy in Zabbix or IP address / DNS name of a proxy not yet known to Zabbix Server (the Proxy must listen on port 10051 in this case).

In the server case, only a host group and the host are created and then the rest is configured (described below). With proxy, the script first checks via Zabbix API, whether a proxy with the specified name exists in Zabbix and if not, it creates a proxy with the technical name `proxy.<suffix>` and interface, where the IP/DNS name is equal to the provided argument and port is 10051. Note that when creating the proxy record in Zabbix, your not yet registered proxy must be configured with the Zabbix host name `proxy.<suffix>`, or the communication will fail. Then, host group and host monitored by the proxy is created. The rest is configured same as with server configuration.

After creating the host, the discovery rule is added to it, with keep lost resources period set to 0. Then, the python list MetricConfigs, containing your configured metrics, is iterated and for each found metric, Zabbix objects are created using the API. First, the User macros with and without context are defined in the scope of the host. The macro names have the pattern `<NAME>_<SEVERITY>:"<PRIORITY>"`, `<NAME>` is the name argument from constructor of the instance converted to upper case, `<SEVERITY>` is name of the severity in upper case (each trigger of each severity has its macros, just like in the example for User macros with context), with a context of a known priority. There's also a default macro for each metric and severity, without the context. Only macros with context for values filled in priority map are created, macros for left out prioritiy/severity pair are not created. Default macros, without context, however are always created and correspond to severities under the special priority -1. If a severity for the special priority -1 is left out (or `None`), the value of the macro `<NAME>_<SEVERITY>` is set to 16777216.

Once the macros are created in the host, item prototypes are created, as mentioned previously with key `<aws_statistic_name>.<aws_metric_name>.metrics.<suffix>[{#FN_NAME}]` of type Zabbix Trapper. Having more metric configs with both aws_statistic_name and aws_metric_name set to same values "shares" the item prototype among them. When the script tries to create the already existing item prototype (the first metric config of the share group created the item protype), it instead does nothing. The triggers of the metric config will however reference that shared item in the expression.

Then, the creation of trigger prototypes is carried on. For each severity starting from Disaster, it is first checked whether the severity is filled out for at least one priority. If not, the trigger prototype is not created. If the severity is at least once not left out, the trigger prototype is created with name `<severity>.<name>.triggers.<suffix>[{#FN_NAME}]` and trigger expression, which is a result of calling the `.format()` method of Python `str` object on the expression pattern, with the first argument of value `/<suffix>/<aws_statistic_name>.<aws_metric_name>.metrics.<suffix>[{#FN_NAME}]` (the 'server', the first `<suffix>` references the host) and the second `<NAME>_<SEVERITY>:\"{#<NAME>_PRIO}\"` (the constant). As the quotes around the context are escaped, the constant in the expression pattern from configuration must be enclosed in quotes.

When a trigger prototype is created, its Zabbix ID is stored and all subsequent triggers prototypes of the metric are made dependent on all stored trigger prototype IDs. On discovery, all discovered triggers are also dependent on triggers of higher severity, thanks to which only one trigger of the metric is fired when an expression evaluates to true, even if lower-severity expressions are true as well.

After macros, item prototype and trigger prototypes of all metrics are created, Override rules (one per configured metric and Lambda priority) are created. Each rule has a filter on the metric's priority LLD macro and evaluates to true when the LLD macro exists and its value is the overrides rule's priority. The operations (modifications) of the Override rule disable discovery and creation of triggers with severities that are left out (or `None`) in the metric config for the specific priority. Additionally, an Override rule for each metric is created for the "unclassified" priority, in config specified by priority -1. Its filter evaluates to true if the priority LLD macro does not exist or the macro does not match any valid priority (negation of all the previous rules' filter). 

As such, Zabbix is configured and the script ends.

### AWS side
The AWS side presumes Zabbix is already configured and starts discovering functions and sending their metrics right away. If Zabbix is not yet configured, both the Discovery Lambda and the Transformation Lambda will keep failing, as Zabbix will not recognize the host and items and will respond with failure.

AWS, or more concretely the AWS CloudWatch service, is in the scenario the collector of metrics. Each invocation of any Lambda function produces a set of metrics characteristic to Lambda functions and logs, including AWS logs about the run of the function and any logs printed during the execution of the function. Metrics and logs are stored in CloudWatch for long-enough (relative to this project) time. This project only cares about metrics and not logs. In AWS, there's a service called Metric Stream, allowing to deliver captured metrics to various locations. The stream generates metric data in one of three formats, depending on configuration, with this project using the JSON fromat. Another part in the Metric Stream configuration is listing the metrics to be streamed. CloudWatch separates metrics to logical namespaces, the one for Lambda functions is called AWS/Lambda. The concrete metrics that enter the stream are silently passed by prj_config.py to SAM parameters JSON based on metrics_def.py, and the parameter JSON is expanded to template parameters during building and deploying the default template (zblamb-sam/metric-stream.yaml) with the sam.py script.

AWS CloudWatch gathers Lambda metrics in 1-minute cycles and stores several aggregated statistics from Lambda functions that have been invoked in the cycle loop. At the end of the cycle, CloudWatch using the Metric Stream puts the metric data to a Kinesis Firehose, an AWS datastreaming serverless service, created along with the Metric Stream. The input of the Firehose is always set to 'DirectPUT' (required by Metric Stream) and the output destination can be set by the user. In this project, the destination is set to an S3 bucket (another AWS service, for storing data objects in so-called buckets), but ideally, no data will be sent to the bucket, as will be discussed in a few paragraphs. Another convenient configuration of the Firehose is a transformation processor that transforms the data incomming to the data stream and outputs new data, which Firehose delivers to its destination. 

In an ideal scenario, we would have the Firehose deliver raw metric stream data or transformed data for Zabbix to a Lambda function, that would transform raw data to Zabbix packet and send it or just send the prepared data to Zabbix. A Lambda function is ideal for such a task, since it is built on top of the serverless architecture, meaning the server the Lambda function runs on is maintained by AWS and we do not have to worry about it, we must take care only of the code that transforms and delivers data to Zabbix. Sadly, a Lambda function is not an option as a destination of a Firehose data stream. This inconvenience can be lifted by delivering the data to a service that can automatically invoke a lambda function upon reception of the data, such as S3, or by setting up an HTTP endpoint as the destination, which could be run on a server, ditching the bonus of not having to deal with servers, or implemented by an API Gateway that calls the Lambda function.

But there is a way to shorten this undirect path and run the transformation and delivery logic sooner in the process. Among the options for the Firehose' transformation processor, there's Lambda processor. These transformations are intended just to pre-process data in the stream and then push them forward, or filter some out, but as a transformation may be a generic Lambda function, we could use this step to transfrom and send data to the Zabbix server or proxy as a side-effect. Such transformation Lambda must conform to the calling convention defined in AWS Firehose documentation. Mainly, the output of the function should be a JSON document containing the transformed data and a result. One of the valid results the function can output is the 'Dropped' result, which instructs Firehose not to deliver the data to its original destination. 

Utilizing this "hack" would solve the problem. It is only required to have an S3 bucket, to which the data will not be delivered. Yet still upon failure of the transformation Lambda, a crash notification is delivered to the bucket, which wasn't a part of the original idea, but we'll call that a feature. Also, when the function fails, it is retried a number of pre-configured (using prj_config.py) times with the same data, and only after all retries fail, the notification is put to the bucket. 

Unsurprisingly, this is the Transformation Lambda mentioned several times in this documentation. How the function processes data will be stated below.

The Firehose data stream can be configured broadly, with other configs such as CloudWatch logging, data compression and encryption, S3 backups of miss-delivered data and data buffering. Actually, there are two types of buffers that can be configured. First, a buffer that stores data before putting them to the transformation Lambda and a buffer of transformed data before sending them further through the Firehose pipe. As we expect the transformed "data" to be dropped, only the first buffer is of interest to us. The buffering can be limited by time period and data volume, whichever is reached first. The higher the period or volume, the more metrics will be pushed to the transform, but it won't be run as frequently and will probably contain several aggregated metrics from CloudWatch, that sends metrics in 1-minute intervals as already stated. In project configuration, you are able to set these limits. All other mentioned Firehose configurations are disabled.

Apart from the Transformation Lambda, the Discovery Lambda is created in the metric-stream.yaml SAM template as well. These do not have priorities defined by default and must be set manually by the user. Operation of both will be described next.

#### Transformation and Discovery Lambdas
The Discovery Lambda is invoked once every pre-configured number of minutes. The number must be more than 2 tough, since the [rate expression](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-scheduled-rule-pattern.html#eb-rate-expressions) requires to use the singular word for a number of 1 and plural for any other number. Seriously, what kind of software developer/engineer comes up with that? Allowing 1 minute would require creating a condition in the template and checking against it. That's too much of a nuisance only for allowing for a rate that won't be likely used, and even if so, one more minute to wait is an acceptable delay. Would adding the condition to the template take less time than writing this rant? Probably. But it needed to be addressed (plus it would be best to test it's working, which would require even more time, more than it took from the start of the rant up to here). 

After the rate is set to a reasonable value (and other parameters filled in as well), an AWS Event Bus Rule is setup for the default Event Bus that invokes the Lambda with the specified rate. The Discovery Lambda lists all Lambda functions using the boto3 package, filters out Lambda functions without the priority environment variable and then, for all remainig functions that do not have an env var that serves as a flag specifying the function is already discovered in Zabbix, flags them with the "flag variable". After flagging functions, it parses the priority variables, which are in format `"<metric_name>:<priority> ..."` and creates JSON data containing a list with objects that have the `{#FN_NAME}` and `{#<METRIC_NAME>_PRIO}` parameters, aka the LLD macros, set to name of the function and its priorities. The JSON list is then sent to Zabbix, using the zappix package. 

The IP address of Zabbix server or proxy is passed via the ZBLAMB_PROXY_IP environment variable, which is set during creation in the metric-stream.yaml SAM template via a user-specified parameter (or can be auto filled, if the zbx_server_proxy.yaml template was used to create Zabbix instances). The port is assumed to be 10051. The function completes execution successfully, if Zabbix replies with a 'success' packet and with 1 processed item. If Zabbix reply is not success, the item failed to process or the total of recieved items is 0 even if the packet was not empty, the Discovery Lambda exits with exit code 1 and logs the error prior to exitting.

The Transformation Lambda is invoked with a Firehose event as its argument. The event is a JSON object with ARN of the Firehose stream, invocation ID and most importantly, an array of records. Each record is again a JSON object with the approximate arrival time, record ID and the data of that record. The data are passed from the Metric Stream and encoded using the base64 binary data encoding scheme. Metric Stream passes a text document including JSON objects, one per line. These JSON objects include the metric statistics, some of which will be pushed to Zabbix. Metric Stream sends the gathered metrics in every possible combination of *dimensions* under the CloudWatch namespace. The dimensions are not really useful to us and since the goal is to monitor Lambda functions, we are only interested in the single dimension 'FunctionName'. More on dimensions can be read in the [AWS CloudWatch documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_Dimension.html). 

Each line of the data Metric Stream sends is a JSON object with a specific dimension combination and therefore, we are only interested in those lines, where only the 'FunctionName' dimension is present, no more or less (a no-dimension JSON is sent as well, aggregating metrics across all functions). The per-line JSON objects sent by Metric Stream also include more administrational information and primarly, the metric name and statistics. Useful to us is also the timestamp field of the object, recording when the metric was measured. The first step in the Transformation Lambda's algorithm is therefore extraction of the JSON objects with a single dimension of 'FunctionName'. For this purpose, the Lambda defines the `extract_data()` function. As a side-effect, `extract_data()` collects names of Lambda functions encountered.

Next, the Lambda runs through the collected Lambda function names and for each, using the boto3 package, discovers, whether it has the priority env var and whether it is flagged by Discovery Lambda as discovered in Zabbix. Names of Lambdas without the env vars are stored in a set of ignored functions. After retrieving the set, the Transformation Lambda moves on to constructing a single packet containing the values for Zabbix items. To know which metrics and statistics to push to Zabbix, there is a silently exported 'metric selection' config during configuration by the prj_config.py script, based on the configured metrics in metrics_def.py. The config is stored as a constant inside the config.py file, generated by prj_config.py.

The metric selection config is a simple python dictionary, where keys are AWS metric names and their values are lists of statistics to push to Zabbix. For example, the config in config.py could be:

        ... # other configs
        AWS_METRIC_SELECT= {'Errors': ['sum'], 'Duration': ['max', 'min']} 

This config tells the Transfromation Lambda it should push the value of the sum statistic of the Errors metric to the `sum.errors.metrics.<suffix>[<FunctionName>]` Zabbix item, then the Duration/max and Duration/min values to their corresponding Zabbix items as well. The Transformation Lambda runs through the extracted JSON objects again and for each, where the Lambda is not in the ignored set, gets all the selected statistics of the current JSON's AWS metric (property metric_name) and for each statistic, constructs an instance of the `SenderData` class of the zappix package, containing all the required information for Zabbix: the host name (taken from ZBX_SUFFIX in config), item name and value (determined by the metric selection config) and also second and nanosecond timestamps generated from the JSON's timestamp provided by Metric Stream (in miliseconds, so two conversions are made). Yes, the actual code iterates through three nested for loops. Inside python's list comprehention syntax. With an 'if' clause. Look at it. It's beautiful. The function `zbx_mass_item_packet()` handles this and returns a list of the `SenderData` objects.

At last, the objects returned by the `zbx_mass_item_packet()` function are sent to Zabbix in a single packet. Address of Zabbix is again yoinked from the ZBLAMB_PROXY_IP environment variable (can be server IP too) and port is 10051. It does some error handling on the response from Zabbix and if all went correctly, returns a response as specified by Firehose. The response from the Transformation lambda is a JSON with a 'records' parameter, a list of objects that each have a 'recordId', which must be the same as provided by Firehose, 'data', which yields the transformed data, base64-encoded, of the record with the unique recordId and a 'result' parameter. In our case, the result is always 'Dropped', instructing Firehose not to push the data anywhere, and thus the data can be an empty string. 

In case Zabbix responds unsuccessfully, or with at least one failed item data, or in case the total number of data seen by Zabbix is less then the number of data created for the packet, the Lambda ends with exit code 1. Since Firehose then does not recieve its response and sees the Lambda failed, it sends a failure description file to the underlying S3 bucket. For a clearer description, see the [AWS Firehose Documentation](https://docs.aws.amazon.com/firehose/latest/dev/data-transformation.html#data-transformation-failure-handling). The file is stored in on path startig with the 'processing-failed' directory and continues with directories named by the date of the failure. The file contains JSON objects (one per line), each object mainly containing the 'rawData' parameter, base64-encoded MetricStream data that were the input to the Transfromation Lambda and other not interesting parameters.

Both functions log some information in the INFO level and in case of error, in the ERROR or FATAL (CRITICAL) level. The log level, below which logs are not printed, can be set with the LOG_LEVEL environment variable in AWS Console after creation or by modifying the metric-stream.yaml template prior to deploying the stack. Default is set to INFO and values can be the valid names of log levels in python: DEBUG, INFO, WARNING, ERROR, CRITICAL.

And this is the whole AWS side of the project. Neat, huh?

#### Optional Mock Lambda
For testing purposes, it is possible to have a Mock Lambda created. It is a simple Lambda Function, that searches for the 'result' keyword in its event argument and if its value is 'pass', the Lambda exits correctly, when the value 'raise' is encoutered, the Lambda raises an exception, on the 'timeout' value, the function times out and in any other case, it returns with an exit code of 1.

## Changing configuration and Adding metrics
Changing configuration to the running project is not supported. To change either the defined metrics in metrics_def.py or configs using prj_config.py, recreate the project with the following:

First, change your metrics_def.py with your new set of metrics (including the old ones you wish to "keep") and then re-run prj_config.py.

Optionally, for cleaner update, go to AWS Console, stop the Metric Stream and disable the EventBridge Event Bus rule under the default Event Bus that schedules the Discovery Lambda. If you do not do this, you might encounter some Transform and Discovery Lambda failures, but these will be quite irrelevant, as the Lambdas will probably be replaced.

If changing the file configuration in prj_config.py or updating the metrics in metrics_def.py in any way, go to your Zabbix' frontend and delete the `group.<suffix>` host group and the `<suffix>` host. If you've created a new record for a Zabbix proxy when you ran scripts.zapi, delete the proxy as well (`proxy.<suffix>`) or keep it, but use the same name when you call scripts.zapi again a bit later, whether or not you're changing the suffix. New metrics cannot be added to an existing host, you have to recreate everything in Zabbix again. Once you've cleared your Zabbix, run scripts.zapi again the same way you ran it before. It re-creates all the objects, possibly with a new suffix, and loads the newly configured metrics.

The AWS side must be changed no matter what configuration you've changed. This step is easier though, it suffices to just re-run SAM tamplate building and deploying using the sam.py script with the exact same command as in setup of the project. First, build the template and then deploy it. This will update the Stack in AWS CloudFormation. If you've disabled the Event Bus rule and stopped Metric Stream, you must start them again now.

The update is complete

### Chaning configuration by running multiple instances of the project
A workaround to deleting stuff in Zabbix and updating the CloudFormation Stack, you could run two instances of this project. First, change the metrics in metrics_def.py (you'll probably want delete old metrics for no duplicities) and re-run prj_config.py, but specify a different ZBX_SUFFIX than your current one(s). You can then call the scripts.zapi module as before to create new Zabbix objects alongside the old ones. 

With AWS though, you will need a bit of a change. Build stays the same, but when calling sam.py deploy, add the `--stack-name <new_stack_name>` option and set the new stack name to a different one that is not yet in your account. The downside to this is that in order to update the old stack, you'd have to configure the project again to the old values, with some changes.

Alternatively, you can clone this repo twice and have two copies of it, just with different configurations. In this case, to avoid specifying the stack name to deploy to each time, you can go to zblamb-sam/samconfig.yaml and under default global parameters, change stack name (line 8 of the file) to your different stack name.