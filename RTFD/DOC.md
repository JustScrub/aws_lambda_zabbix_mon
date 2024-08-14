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
 - Apart from items, 'host' also has 'triggers', an object that sets off a problem / an event of a specific *severity* (Not Classified, Information, Warning, Average, High, Disaster) when the 'trigger's expression evaluates to true. The user is required to know how to write trigger expressions. Read Zabbix documentation of your Zabbix version. Note that expressions include a function, *host and item name* as input to the function and a *constant* the output of the function is compared against.
 - For discovery rules, item and trigger prototypes are defined: stubs of items and triggers that will be filled in and created concretely for every discovered entity.

Lambda priority to Zabbix severities transformation:
 - This project defines a number of Lambda *priorities* (0-4), specified in the lambda's tags
 - Each Lambda priority is mapped to a subset of Zabbix severities, creating pairs (*priority*,*severity*)
    - so if priority 2 is mapped to {Warning,High}, the pairs are (2,Warning), (2,High)
 - each pair of the mapping is assigned a *constant* used in trigger expression
 - There is one such mapping (priority,severity) -> constant for **each** configured metric
    - note that metric has several meanings already: an AWS metric, a metric as a configuration primitive of this project, and a single measurable value. 

As for the configuration, metrics are instances of the class LLDMultiTriggerMetricConfig (in python), which are defined in a list MetricConfigs in the file (python script) metrics_def.py at the root of the project. There are some sample metric configs pre-defined as examples. Instances in the list server as central configuration of the "metrics" in Zabbix (items and triggers) and of AWS function stream the metrics to Zabbix (which AWS metrics and statistics to stream to which Zabbix items). The constructor of each instance needs the following:

 - zbx_name = name of the "metric" in Zabbix and for the user to distinguish. Must only include characters allowed in Zabbix item names. The item name will be `<zbx_name>.metrics.<suffix>[<FunctionName>]`, suffix will be explained below (ZBX_SUFFIX config and naming conventions) and FunctionName is name of the Lambda Function, filled in automatically using Zabbix discovery.
 - zbx_value_type = data type of the item in zabbix. Allowed values are "int","float","text","log" and "char" ("int" is unsigned in zabbix)
 - aws_metric_name = name of the metric in AWS CloudWatch. See the monitored metrics of Lambda Functions by CloudWatch in AWS documentation. Interesting ones are 'Invocations', 'Errors' and 'Duration'. AWS CloudWatch accumulates metrics over 1 minute and provides aggregated values. Aggregated values are then buffered for a configured time period before ultimately sent to Zabbix. The metric name must be equal to the name in AWS, including character case!
 - aws_statistic_name = name of the statistic to take from the specified aws_metric_name. AWS provides several statistics (sum,min,max,count) for each accumulated metric you can choose from. You can also add more statistics, but has to be configured manually (explained later). For metrics Invocations and Errors, use the sum statistic (as per AWS documentation). The name must be same as in AWS, case-sensitive.
 - priority_mapping = mapping of Lambda priorities to Zabbix severities and constants. A table implemented with nested dictionaries. See below.
 - zbx_trigger_expression_pattern = pattern of the expression for each trigger prototype of the metric's item prototype. There's one item prototype per class instance. An item prototype has a trigger for each severity except those severities, that aren't defined for any priority in the mapping. Each of these trigger prototypes has the same expression. They will differ slightly for each Lambda function once a Lambda is discovered (function name and priority will be filled in). On how to specify the expression pattern, see below.

The first four fields are self-explanatory, the last two need special care. The priority mapping is a dictionary, where keys are instances of the LambdaPriority class defined in the scripts.zapi python module. Not all priorities must be present in the dictionary, some may be left out. There can also be a special priority with the value -1, that will be used for any invalid or left out priority. The values of the keys (which are Lambda priorities) are nested dictionaries. These nested dictionaries have keys corresponding to Zabbix severities, represented by the ZabbixSeverity enum class defined in the scripts.zapi module. Severities may be left out as well. The values of these severities are the constants used in trigger expression. This may all seem confusing yet, but there will be examples ahead. Leaving a severity out for each Lambda priority results in not creating the trigger prototype with that severity. Triggers are also created dependent on each other, lower severity depends on higher (i.e. when trigger with higher severity is set off, lower severity triggers are not, thanks to which Zabbix dashboard is not spammed with multiple problems revolved around the same function -- only the highest severity problem is shown). You can also 'leave out' a severity by specifying the constant as python's `None`. Whey you leave out a priority, discovered functions of that priority will fall under the special priority -1. If even priority -1 is left out, only items of the discovered functions will be created from the item prototype, without any triggers. If you leave out a severity under a priority, the trigger of that severity will not be discovered for function with the priority. If you leave out a severity for every priority, the trigger prototype will not be created (because no function, no matter its priority, would discover it).

Zabbix trigger expression patterns are trigger expressions with left-out 'server' and constant, against which the result of function called on the 'server' is compared. The 'server' in Zabbix terms is unique identificator of an item and consists of Zabbix host name and the item name. Both the server and the constant will be inserted programatically. The user only has to specify where in the expression they should be filled in. The expression pattern is a string on which the python's `format` method will be called with server and constant as arguments, in this order. If in place of the server and constant is the `{}` string, they will be replaced in that order. A more fault-proof way would be to specify `{0}` in place of the server and `{1}` in place of the constant. This way, you can even have multiple functions and comparations in the expression. **It is highly important that the constant term is surrounded by quotes (")!** I.e. there are quotes around each `{1}` (or the second `{}`).

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

This instance defines a `max.duration.metrics.<suffix>[{#FN_NAME}]` item prototype in Zabbix, where `<suffix>` will be set in the next configruation steps and `{#FN_NAME}` is a macro that will be expanded with a Lambda function name, once it is discovered. The values are real floating numbers. To this item (of discovered Lambdas), values form the AWS CloudWatch Duration metric's max statistic will be pushed -- i.e. the maximum duration of all accumulated lambda invocations. If a Lambda is invoked 3 times in a minute and operated for 250.0 ms the first time, 370.0 ms the second time and 240.0 ms the last time, the value 370.0 will be forwarded by AWS Metric Stream. The expression will evaluate to true when the last value (the last maximum duration) is higher than a constant specified in the priority_mapping table. In the table, only 3 priorities are defined. For functions with priority 0, a DISASTER trigger will fire, if the last maximum duration was 1 second or more (Duration is measured in miliseconds). For functions with priority 1, HIGH trigger will fire, if at least one invocation of the function took 750 ms or more and DISASTER if it took 1500 ms or more. With functions of priority 2, AVERAGE will set off in case an invocation took half a second or more and HIGH trigger when it took a second or more. Other priorities, including undefined ones, will not fire any triggers, because the key `LambdaPriority(-1)` is left out. Note that for the Duration metric, the 'max' statistic tracks "if at last one function took more than X ms", whereas the 'min' statistic tracks "if all functions took more than X ms". Also Note that in this case, the expression could be `'last({})>="{}"'`, since item identification is first and constant is second, without additional references to the two. In Zabbix, one item prototype will be created along with three trigger prototypes: of the severities Disaster, High and Average, other severities are left out for all priorities. On discovery of function with priority 0, only the Disaster trigger will be discovered and the rest two won't.

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

Creates item prototype with name `count_avg.duration.metrics.<suffix>[{#FN_NAME}]` of data type float, the concrete items of which will be fed with the minimum duration of CloudWatch accumulated metrics of the function. The expression triggers if for the last 15 minutes, at least 7 times all function invocations in a batch of accumulated invocations took more than constant or the average of minimum durations within the 15 minutes was greater than the constant. The constants depend on the priority_mapping table. Functions of priority 0,3,4 and all undefined priorities will fall under the third priority, -1. Priority 1 functions trigger HIGH if 7 or more batches took at least 1500 ms or the average was more than 1500 ms, and trigger AVERAGE if it was 1000 ms. Priority 2 functions only trigger AVERAGE (HIGH is set to None and other severities are left out) with the constant set to 1500 ms. Functions with any other priority trigger NOT_CLASSIFIED for the constant 3000 ms.

That's it for metrics definitions. You can define how many metrics you wish, but with more metrics, more computing on Zabbix and in AWS is required. This was also the hardest thing to configure, so congrats. It should be chill from now on.

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

        python3 sam.py build -t demo.yaml ./template_params.json && pyhon3 sam.py deploy [--guided] ./template_params.json

This sets the whole project up with demo metrics as well, not the metrics you may have defined yourself. To change the metrics, update the stack as described in one of the sections below. For the demo to work, you'll need to configure zabbix and start monitoring your Lambdas, as described in the next sections. The AWS application is set up in demo. However, after configuring Zabbix (via frontend running on Server), you might need to restart the instances and possibly the Metric Stream and Event Bridge driving the Transform and Discovery lambdas, respectively. Also, as this is just a demo app, many parameters are left to their defaults without inputting your submitted parameters. 

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
In Zabbix, this project names objects "hierarchically" in a tree manner, with layers separated by commas and the root of the tree being the ZBX_SUFFIX config value. Zabbix host group, to which the host belongs, is called `group.<suffix>`, the host is the top-level object named just `<suffix>`, its LLD rule `discovery.<suffix>`. The item prototypes of each metric are named `<zbx_name>.metrics.<suffix>[{#FN_NAME}]`, where `<zbx_name>` is the zbx_name argument to LLDMultiTriggerMetricConfig constructor when configuring metrics and `{#FN_NAME}` is a LLD macro used in Zabbix, that will expand to the function name once it's discovered. The concrete item is thus "parametrized", as per Zabbix documentation, with the function name. This might seem to break the convention, but Zabbix's method of item parametrization is utilized. The name of the item is the "tree path" `<zbx_name>.metrics.<suffix>`, conforming to the convention, and is parametrized by the function name, which in Zabbix is noted by appending with `[<FunctionName>]`. The trigger prototypes, generated for each item prototye, are named `<severity>.<zbx_name>.triggers.<suffix>[{#FN_NAME}]` with `<severity>` beign the name of Zabbix severity in upper case, as up to six triggers (one for each Zabbix severity) are created for each item. The same parametrization scheme as in items is utilized (although Zabbix does not mention parametrization of triggers, but it is at least consistent with item names). If you've created Zabbix Proxy using the zbx_server_proxy template, the proxy's Zabbix host name is `proxy.<suffix>`.

If you wish to continue this convention in your environment, you may name your metrics in a similiar manner. For example, if you create more metrics from AWS Duration metric, you may use a pattern like `<concrete_metric>.duration` for the zbx_name argument to the LLDMultiTriggerMetricConfig constructor. The sample metrics in metrics_def.py that come with the repository utilize this.

## How it works
The project comprises of two components: Zabbix setup and AWS infrastructure. In Zabbix, multiple features are utilized and objects are setup using a python module in this repo, with path `scripts.zapi`. Note that this project was written for **Zabbix version 5.4**, some things may be different in other versions. In AWS, the main components are the Transformation Lambda and the Discovery Lambda. The former gets called with a batch of AWS metrics and their statistics and it transforms these to a packet Zabbix understands, with the correct host and item filled in, and sends the packet, delivering the configured AWS metrics to configured Zabbix items. The Transformation Lambda is fed by an AWS Metric Stream through an AWS Kinesis Firehose Datastreaming service. The concrete logistics will be discussed later. 

The Discovery Lambda gets called in configured intervals using AWS Event Bridge wihtout any arguments and the Lambda Function lists all Lambdas in your account and region, filters out Lambda functions without the priority tag, then to the remaining found Lambdas adds another tag, flagging the function as discovered, and discovers these functions in Zabbix. All functions are discovered, even those with the Zabbix discovered flag tag. This is a specification of Zabbix and discovery is intended to work like that. The Transformation Lambda too filters functions without the priority flag and functinons without the Zabbix discovered flag (because it does not exist in Zabbix yet).

### Zabbix side
On the Zabbix side, the main component is the Zabbix host named `<suffix>` (configured with ZBX_SUFFIX config). As hosts in Zabbix must belong to a group, a host group `group.<suffix>` is created. The host is created with a single "LLD rule" `discovery.<suffix>`, a quasi-item that accepts data in the JSON format containing a list of object, each object includes parameters named the same as "LLD macros", and their values are the values of these macros. The LLD rule can be of various types like any other Zabbix item, but in this project, only Zabbix Trapper is utilized. For clearer information, consult [Zabbix 5.4 Documentation](https://www.zabbix.com/documentation/5.4/en/manual/discovery/low_level_discovery). For this project, the macros are `{#FN_NAME}` and `{#PRIO}` that expand to the discovered Lambda Function name, resp. its priority. 

AWS Discovery Lambda is expected to send the JSON list containig objects with these macros, and the rest is handeled by Zabbix. LLD rules in Zabbix have their item and trigger prototypes (and might have host and graph prototypes, not used in this project). The prototypes are much like normal items and triggers, but the name and trigger expression are parametrized with LLD macros. Once a fucntion is discovered, i.e. the LLD rule accepts a valid JSON list with LLD macros, Zabbix creates items and triggers, but with the LLD macros in their prototypes substituted with the values from the JSON list. 

For example, when an LLD rule with item prototype with name `errors.metrics.lambda[{#FN_NAME}]` and trigger prototypes with expression `last(lambda/errors.metrics.lambda[{#FN_Name}]) > "ERRORS:\"{#PRIO}\""` accepts the data 

        [ 
            { "{#FN_NAME}": "my_lambda",       "{#PRIO}": "2" }, 
            { "{#FN_NAME}": "my_other_lambda", "{#PRIO}": "1" } 
        ]

the items named `errors.metrics.lambda[my_lambda]` and `errors.metrics.lambda[my_other_lambda]` and triggers with expression `last(lambda/errors.metrics.lambda[my_lambda]) > "ERRORS:\"2\""` and also triggers with the expression `last(lambda/errors.metrics.lambda[my_other_lambda]) > "ERRORS:\"1\""` would be created. We'd say that the functions my_lambda and my_other_lambda were discovered and that the created items and triggers were discovered.

Another important parameter of LLD rules is the keep lost resources period. Zabbix mentality is that every subsequent discovery packet should contain all previously discovered entities, not only newly discovered. If an entity that was previously discovered is not included in the next discovery packet (i.e. JSON object with its LLD macros is not present in the packet), Zabbix marks the objects of that entity (items and triggers) as "no longer discovered" and starts a counter for the objects set to the keep lost resources period. If the LLD macros do not show up in one of the subsequent packets recieved prior to the counter's deadline, the objects are deleted from Zabbix once a packet arrives after the deadline that does not contain the LLD macros as well. 

Since the Discovery Lambda lists all existing Lambda functions in an account with the priority tag and sends all of them in the discovery packet, the keep period is set to 0, meaning the Zabbix objects are deleted immidiately when a function is not re-discovered. This allows for easy Lambda deletion and priority updates. Deleting a function in AWS results in not sending it in the next packet, which removes the function altogether from Zabbix. Updating the priority tag value deletes all objects with the old priority and sets up new objects for the new one: and as item prototypes only include the function name, the items and their data history are preserved and only triggers are re-created with the right priority. Deleting the priority tag "unsubscribes" the function from being monitored by Zabbix.

Apart from just discovering items and triggers, LLD rules can have "Overrides". These are rules that modify the objects to be created prior to their creation, allowing for more configurability. Overrides have a filter, which is a condition on the accepted LLD macros, e.g. in the form '{#PRIO} is equal to "3"', name of the object to modify and rules on how to modify the object. One of the modifications is whether to discover the object, thus allowing not to discover (or create) triggers that are not required in the context of incomming priority, based on the metric configuration. For example, with the priority mapping

        priority_mapping={
            LambdaPriority(0): { ZabbixSeverity.DISASTER: 0 },
            LambdaPriority(1): { ZabbixSeverity.DISASTER: 1,   ZabbixSeverity.HIGH: 0},    
            LambdaPriority(2): { ZabbixSeverity.HIGH: 2, ZabbixSeverity.AVERAGE: 0},        
        }

trigger prototypes are created with the Disaster, High and Average severities. These must be created, because the priorities of all functions are not known apriory, but only after the discovery, so they "must be prepared". Other severity triggers however will never be needed for this item, it is left out across all specified priorities, so there is no need to create prototypes of these severities. Then, after the arrival of discovery packet with a function of priority 0, the triggers of High and Average severity are not required according to the mapping, so they can be left out of discovery. This is the exact use case of Overrides in this project. 

In Override filters, only LLD macros can be compared. This means all metrics defined in Zabbix (as configured in metrics_def.py) must be modified under single Override rule. Hence, the number of Overrides is exactly the number of priorities. On reception of function and its priority in discovery, all triggers of the newly discovered function are updated in a single Override, across all metrics.

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

we could write the Disaster trigger prototype expression as `last(lambda/errors.metrics.lambda[{#FN_NAME}]) > "ERRORS_DISASTER:\"{#PRIO}\""` and the High and Average trigger prototypes accordingly. Then upon recieving a discovery packet, the constant in the expression (the right-hand side) is expanded by Zabbix, according to the priority mapping. Discovering a function therefore automatically fills in the right constant, as configured in the mapping. See [Zabbix Documentaton](https://www.zabbix.com/documentation/5.4/en/manual/config/macros/user_macros_context) on User macros with context.

Just a quick note on quoting nad context-less macros. For some reason, in order to work, both the macro and its context must be quoted. Since the context is a part of the macro name, the quotes around it must be escaped. Without quotes, Zabbix fails to correctly expand the LLD macro upon discovery, the reason is not known. The context-less macros serve for the special priority -1 in mapping: if an undefined priority is discovered, the context name containing the undefined priority is not found and the default macro is expanded, just like the `ERRORS:"not-defined"` example. Default macros should be defined even if undefined priorities have no triggers (-1 priority left out in mapping, or all severities have a value of `None`) to make Zabbix happy. In this case, the default macro values are set to very high numbers, so that is is very improbable for any mal-discovered trigger to set off.

The Zabbix configuration script relies on the mentioned features – LLD rule, item and trigger prototypes, Overrides, User macros (with context) – to make purely Zabbix handle the whole discovery and taking care of accepted metrics. With rightly configured, Zabbix only needs to recieve discovery packets to the LLD rule quasi-item and metric packets to corresponding items, once they are discovered. Sending of these packets is handeled by the AWS side of the project.

#### Zabbix configuration script flow
Now that the used features are described, let's have a look how the configuration script operates.

The scripts is called as a python module, scripts.zapi, that includes the script `__main__.py` that gets invoked. The script requires three or four arguments, depending on your Zabbix infrastructure. If you intend to push metrics to Zabbix Server directly, the script is called with three arguments, IP address or DNS name and port of Zabbix Frontend (running the API, which the script uses) and the argument "server". If metrics should be pushed via a Proxy, there are four agruments, the first two remain the same and the other two are "proxy" and a technical name of an existing proxy in Zabbix or IP address / DNS name of a proxy not yet known to Zabbix Server (the Proxy must listen on port 10051 in this case).

In the server case, only a host group and the host are created and then the rest is configured (described below). With proxy, the script first checks via Zabbix API, whether a proxy with the specified name exists in Zabbix and if not, it creates a proxy with the technical name `proxy.<suffix>` and interface, where the IP/DNS name is equal to the provided argument and port is 10051. Note that when creating the proxy record in Zabbix, your not yet registered proxy must be configured with the Zabbix host name `proxy.<suffix>`, or the communication will fail. Then, host group and host monitored by the proxy is created. The rest is configured same as with server configuration.

After creating the host, the discovery rule is added to it, with keep lost resources period set to 0. Then, the python list MetricConfigs, containing your configured metrics, is iterated and for each found metric, Zabbix objects are created using the API. First, the User macros with and without context are defined in the scope of the host. The macro names have the pattern `<ZBX_NAME>_<SEVERITY>:"<PRIORITY>"`, `<ZBX_NAME>` is the zbx_name argument from constructor of the instance in upper case, `<SEVERITY>` is name of the severity in upper case (each trigger of each severity has its macros, just like in the example above), with a context of the priority of discovered functions. There's also a default macro for each metric and severity, without the context. Only macros with context for values filled in priority map are created, macros for left out prioritiy, severity pair are not created. Default macros, without context, however are always created and correspond to severities under the special priority -1. If a severity for the special priority -1 is left out (or `None`), the value of the macro `<ZBX_NAME>_<SEVERITY>` is set to 16777216.

Once the macros are created in the host, item prototypes are created, as mentioned previously with key `<zbx_name>.metrics.<suffix>[{#FN_NAME}]` of type Zabbix Trapper. Then, the creation of trigger prototypes is carried on. For each severity starting from Disaster, it is first checked whether the severity is filled out for at least one priority. If not, the trigger prototype is not created. If the severity is at least once not left out, the trigger prototype is created with name `<severity>.<zbx_name>.triggers.<suffix>[{#FN_NAME}]` and trigger expression, which is a result of calling the `.format()` method of Python `str` object, with the first argument of value `/<suffix>/<zbx_name>.metrics.<suffix>[{#FN_NAME}]` (the 'server', the first `<suffix>` references the host) and the second `<ZBX_NAME>_<SEVERITY>:\"{#PRIO}\"` (the constant). As the quotes around the context are escaped, the constant in the expression pattern from configuration must be enclosed in quotes.

When a trigger prototype is created, its Zabbix ID is stored and all subsequent triggers prototypes of the metric are made dependent on all stored trigger prototype IDs. On discovery, all discovered triggers are also dependent on triggers of higher severity, thanks to which only one trigger of the metric is fired when an expression evaluates to true, even if lower-severity expression are true as well.

After macros, item prototype and trigger prototypes of all metrics are created, Override rules (one per Lambda priority) are created. Each rule has a filter on the priority LLD macro and evaluates to true when the LLD macro has same value as the priority of the rule. Filters are configured such that if a filter passes, only the modifications in this Override are applied and all subsequents Overrides are skipped. Then for each configured metric, the Override operations on the metric's triggers are added to the Override. Each operation disables discovery of triggers, where the values in priority map are left out (or are `None`). There are up to six (number of severities) override operations per metric in the Override for a specific priority. Lastly, an Override rule is created for the special priority -1 in the same manner, but without a filter, therefore applying to all values of the priority LLD macro that have not been registered by a previous Override rule.

As such, Zabbix is configured and the script ends.

### AWS side
The AWS side presumes Zabbix is already configured and starts discovering functions and sending their metrics right away. If Zabbix is not yet configured, both the Discovery Lambda and the Transformation Lambda will keep failing, as Zabbix will not recognize the host and items and will respond with failure.

AWS, or more concretely the AWS CloudWatch service, is in the scenario the collector of metrics. Each invocation of any Lambda function produces a set of metrics characteristic to Lambda functions and logs, including AWS logs about the run of the function and any logs printed during the execution of the function. Metrics and logs are stored in CloudWatch for long-enough (relative to this project) time. This project only cares about metrics and not logs. In AWS, there's a service called Metric Stream, allowing to deliver captured metrics to various locations. The stream generates metric data in one of three formats, depending on configuration, with this project using the JSON fromat. Another part in the Metric Stream configuration is listing the metrics to be streamed. CloudWatch separates metrics to logical namespaces, the one for Lambda functions is called AWS/Lambda. The concrete metrics that enter the stream are silently passed by prj_config.py to SAM parameters JSON based on metrics_def.py, and the parameter JSON is expanded to template parameters during building and deploying the default template (zblamb-sam/metric-stream.yaml) with the sam.py script.

AWS CloudWatch gathers Lambda metrics in 1-minute cycles and stores several aggregated statistics from Lambda functions that have been invoked in the cycle loop. At the end of the cycle, CloudWatch using the Metric Stream puts the metric data to a Kinesis Firehose, an AWS datastreaming serverless service, created along with the Metric Stream. The input of the Firehose is always set to 'DirectPUT' (required by Metric Stream) and the output destination can be set by the user. In this project, the destination is set to an S3 bucket (another AWS service, for storing data objects in so-called buckets), but ideally, no data will be sent to the bucket, as will be discussed in a few paragraphs. Another convenient configuration of the Firehose is a transformation processor that transforms the data incomming to the data stream and outputs new data, which Firehose delivers to its destination. 

In an ideal scenario, we would have the Firehose deliver raw metric stream data or transformed data for Zabbix to a Lambda function, that would transform raw data to Zabbix packet and send it or just send the prepared data to Zabbix. A Lambda function is ideal for such a task, since it is built on top of the serverless architecture, meaning the server the Lambda function runs on is maintained by AWS and we do not have to worry about it, we must take care only of the code that transforms and delivers data to Zabbix. Sadly, a Lambda function is not an option as a destination of a Firehose data stream. This inconvenience can be lifted by delivering the data to a service that can automatically invoke a lambda function upon reception of the data, such as S3, or by setting up an HTTP endpoint as the destination, which could be run on a server, ditching the bonus of not having to deal with servers, or implemented by an API Gateway that calls the Lambda function.

But there is a way to shorten this undirect path and run the transformation and delivery logic sooner in the process. Among the options for the Firehose' transformation processor, there's Lambda processor. These transformations are intended just to pre-process data in the stream and then push them forward, or filter some out, but as a transformation may be a generic Lambda function, we could use this step to transfrom and send data to the Zabbix server or proxy as a side-effect. Such transformation Lambda must conform to the calling convention defined in AWS Firehose documentation. Mainly, the output of the function should be a JSON document containing the transformed data and a result. One of the valid results the function can output is the 'Dropped' result, which instructs Firehose not to deliver the data to its original destination. Utilizing this "hack" would solve the problem. It is only required to have an S3 bucket, to which the data will not be delivered. Yet still upon failure of the transformation Lambda, **TODO** is delivered to the bucket, which wasn't a part of the original idea, but we'll call that a feature. Unsurprisingly, this is the Transformation Lambda mentioned several times in this documentation. How the function processes data will be stated below.

The Firehose data stream can be configured broadly, with other configs such as CloudWatch logging, data compression and encryption, S3 backups of miss-delivered data and data buffering. Actually, there are two of buffers that can be configured. First, a buffer that stores data before putting them to the transformation Lambda and a buffer of transformed data before sending them further through the Firehose pipe. As we expect the "data" to be dropped, only the first buffer is of interest to us. The buffering can be limited by time period and data volume, whichever is reached first. The higher the period or volume, the more metrics will be pushed to the transform, but it won't be run as frequently and will probably contain several aggregated metrics from CloudWatch, that sends metrics in 1-minute intervals as already stated. In project configuration, you are able to set these limits. All other mentioned Firehose configurations are disabled.

Apart from the Transformation Lambda, the Discovery Lambda is created in the SAM template as well. Operation of both will be described next.

#### Transformation and Discovery Lambdas



## Changing configuration and Adding metrics