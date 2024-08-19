
py_configs = {
    "ZBX_SUFFIX":{
		"value":'zblamb',
		"descr":'Zabbix objects base/root name'},
    "AWS_PRIO_TAG":{
		"value":'PRIO',
		"descr":'Name of Lambda Functions Tag that yields the function\'s priority'},
    #"AWS_TRANSFORM_TIMEOUT":{
    #    "value": '5s',
    #    "descr": 'Timeout of the Transformation Lambda, in zabbix time unit format (number of seconds or a number with s,m as suffix). Minimum 1 seconds, maximum 900 seconds (15m). This option will be propagated to SAM parameters as well.',
    #}
}
PY_CONFIG_FILES = [
        "scripts/config/__init__.py",
        "zblamb-sam/functions/basic_handler/config.py",
        "zblamb-sam/functions/discovery_handler/config.py"
        ]

sam_parameters = {
  "ZBLambDummyDeliveryStreamBucket":{
		"value":'',
		"descr":"An S3 bucket ARN, the destination of the Kinesis Firehose Delivery stream. Only failed invocations of Transform Lambda will be delivered.\nIt is highly recommended to fill this config in now, or use the --guided option to SAM CLI later"},
  "ZBLambTransformBufferingSeconds":{
    "descr": "Duration in seconds how long Metric Stream Firehose buffers data before sending them to the Transformation lambda, in range 0-900 (both inclusive)",
    "value": "60",
    "check": lambda v: 0 <= int(v) and int(v) <= 900, "fallback": 60},
  "ZBLambTransformBufferingMegabytes":{
    "descr": "Data size in MBs (2^20 B) how much Metric Stream Firehose buffers data before sending them to the Transformation lambda, in range 0.2-3 (both inclusive)",
    "value": "1.0",
    "check": lambda v: 0.2 <= float(v) and float(v) <= 3.0, "fallback": 1.0},
  "ZBLambTransformationLambdaRetries":{
      "descr": "Number of retries to invoke the Transformation Lambda, should it fail",
      "value": "1"},
  "ZBLambCreateMockLambda":{
      "value": 'yes',
      "descr": "Whether to create a Lambda function that can fail or pass on demand. Created in metric-stream template.",
      "check": lambda v: v in ["yes", "no"], "fallback": "yes"},
  "ZBLambLambdaTimeout":{
      "value": 5,
      "descr": "Timeout of the Transform and Discovery Lambdas in seconds. Max 5 minutes (300 seconds), as per AWS Firehose documentation",
      "check": lambda v: int(v) > 0 and int(v) <= 300, "fallback": 5},
  "ZBLambDiscoveryRate":{
      "value": 60,
      "descr": "The rate of invoking the Discovery Lambda (how often to discover functions in AWS), in minutes. Must be more than 1.",
      "check": lambda v: int(v)>1, "fallback": 60},
  "ZBLambZabbixIP": {
      "value": '',
      "descr": "IP address or DNS name of Zabbix Proxy/Server. If you plan to create Zabbix EC2 instance(s) using zbx_server_proxy template, leave this blank."},
  "ZBLambLambdasInVPC":{
      "value": 'yes',
      "descr": "Whether to put Transform and Discovery Lambdas inside a VPC. Could be useful if Zabbix is inside the same VPC as well. Options: yes, no",
      "check": lambda v: v in ["yes", "no"], "fallback": "yes"},
  "ZBLambVPC":{
		"value":'',
		"descr":'The VPC ID under which to run EC2 instances created in zbx_server_proxy template and under which to put Transfrom and Discovery Lambdas (if putting them inside a VPC).\nIf creating network using networking template, leave blank.'},
  "ZBLambPrivSubnet":{
		"value":'',
		"descr":'A private subnet ID. Must belong to ZBLambVPC. Used in zbx_serv_proxy for Proxy instance (if creating a Proxy) and for Transform and Discovery Lambdas in metric-stream template (if putting them inside a VPC)\nIf creating network using networking template, leave blank.'},
  "ZBLambPubSubnet":{
		"value":'',
		"descr":'A public subnet ID. Must belong to ZBLambVPC. Used in zbx_serv_proxy for Server.\nIf creating network using networking template, leave blank.\nIf you have a way to connect to a VPC instance other than public IP (e.g. via VPN), you may specify ID of a private subnet in ZBLambVPC.'},
  "ZBLambSSHRange":{
		"value":'0.0.0.0/0',
		"descr":'CIDR range of IP addresses able to connect via SSH, for instances created using zbx_server_proxy template'},
  "ZBLambHTTPRange":{
		"value":'0.0.0.0/0',
		"descr":'CIDR range of IP addresses able to connect to ports 80, 8080, 443 and 8443, for instances created using zbx_server_proxy template'},
  "ZBLambZBXPortRange":{
		"value":'0.0.0.0/0',
		"descr":'CIDR range of IP addresses able to connect to Zabbix ports 10050 and 10051, for instances created using zbx_server_proxy template and for Lambdas from metric-stream template, if putting the Lambdas inside a VPC.\nRecommended the range of specified VPC.'},
  "ZBLambInstanceType":{
		"value":'t3a.micro',
		"descr":'Type of EC2 instances created inside zbx_server_proxy template.'},
  "ZBLambImage":{
		"value":'ami-04f1b917806393faa',
		"descr":'Image of EC2 instances created inside zbx_server_proxy template.'},
  "ZBLambDBUser":{
		"value":'zabbix',
		"descr":'Zabbix DB user login, for instances created in zbx_server_proxy template.'},
  "ZBLambDBPwd":{
		"value":'zabbix',
		"descr":'Zabbix DB user password, for instances created in zbx_server_proxy template.'},
  "ZBLambCreateProxy":{
      "value": 'yes',
      "descr": "Whether to create Zabbix Proxy (or just Zabbix Server) in the zbx_server_proxy template.",
      "check": lambda v: v in ["yes", "no"], "fallback": "yes"},
  "DemoCreateNetwork":{
      "value": 'no',
      "descr": "Whether to create VPC and subnets in demo template",
      "check": lambda v: v in ["yes", "no"], "fallback": "no"},
#  "ZBLambCreditSpec":{
#		"value":'standard',
#		"descr":'',
#       "check": lambda v: v in ["standard", "unlimited"], "fallback": "standard"},
}

docker_env = {
    "PHP_TZ": {
        "value": "Europe/Prague",
        "descr": "Zabbix Timezone in PHP format"
    }
}

class TermColors:
    cols = dict(
        description = "\033[32m",
        config = "\033[91m",
        value = "\033[33m",
        input = "\033[94m",
        default = "\033[0m"
    )

    @classmethod
    def __get_colored(cls,color, str):
        return f"{TermColors.cols.get(color,cls.cols['default'])}{str}{TermColors.cols['default']}"

    def __getattr__(self,attr):
        if attr in TermColors.cols:
            return lambda s: self.__get_colored(attr,s)
        else: raise AttributeError(f"unknown color scheme: {attr}")

def update_config(cfg_dict):
    c = TermColors()
    for k in cfg_dict:
        try:
            print(c.description(cfg_dict[k]['descr']))
            cfg_dict[k]['value'] = input(f"{c.config(k)} ({c.value(cfg_dict[k]['value'])}): {c.cols['input']}") or cfg_dict[k]['value']
            print(c.cols['default'])
        except KeyboardInterrupt:
            print(c.cols['default'])
            return False
    return True

def cfg_checks(cfg_dict):
    for k in cfg_dict:
        if not "check" in cfg_dict[k]: continue
        try:
            passed = cfg_dict[k]["check"](cfg_dict[k]["value"])
        except:
            passed = False
        if passed: continue
        print(f"Illegal value of {k}: {cfg_dict[k]['value']}. Falling back to default: {cfg_dict[k]['fallback']}")
        cfg_dict[k]['value'] = cfg_dict[k]['fallback']


def cfg2tup(cfg_dict):
    return map(lambda e: (e[0],e[1]['value'],e[1]['descr']), cfg_dict.items())

__time_unit_to_secs_dict = {
    's': 1,
    'm': 60,
    'h': 3600,
    'd': 86400,
    'w': 604800
}
def __time_units_to_secs(value):
    """
    Converts time with unit suffix as specified by Zabbix documentation to seconds. 
    :param value: string in format specified at https://www.zabbix.com/documentation/5.4/en/manual/appendix/suffixes
    """
    if type(value) == int: return value
    mult = __time_unit_to_secs_dict.get(value[-1],0)
    try:
        return int(value[:-1])*mult if mult else int(value)
    except:
        return value

def metric_select():
    from metrics_def import MetricConfigs
    if len( set(type(metric) for metric in MetricConfigs) ) != 1:
        print("Metrics in metrics_def.py MetricConfigs must be of one type and the list cannot be empty!")
        exit(1)

    json_dict = {}
    for metric in MetricConfigs:
        if metric.aws_metric not in json_dict:
            json_dict[metric.aws_metric] = [metric.aws_stat]
            continue

        if metric.aws_stat not in json_dict[metric.aws_metric]:
            json_dict[metric.aws_metric].append(metric.aws_stat)
            continue

    return json_dict
        

import json
if __name__ == "__main__":
    c = TermColors()
    print(c.description("Python scripts and AWS SAM template parameters config."))
    print(c.config("To cancel filling out a config, press CTRL+C - this will not write the config"))
    input(c.value("Press enter to continue"))

    metsel = metric_select()
    print("Configuring python scripts\n")
    if update_config(py_configs):
        py_configs.update({
            # ZBX configs the user does not need to know about
            "ZBX_LLD_KEEP_PERIOD": {
                "value": 0, #__time_units_to_secs(py_configs['ZBX_LLD_KEEP_PERIOD']['value']),
                "descr": 'How long Zabbix keeps discovered entities in seconds if no new data have been recieved'
                #"check": lambda v: v == 0 or (3600 <= v and v <= 788400000), "fallback": 2592000
            },
            "ZBX_PRIO_MACRO":{
                "value":'PRIO',
                "descr":'Zabbix LLD Macro that yields the discovered function priority'
            },
            "ZBX_FN_NAME_MACRO":{
                "value":'FN_NAME',
                "descr":'Zabbix LLD Macro that yields the discovered function name'
            },
            # set number of Lambda priorities
            "N_LAMBDA_PRIORITIES": {
                "value": 5,
                "descr": "Number of Lambda priorities"
            },
            # Lambda Tag Name that tags the functions it is discovered in Zabbix
            "AWS_DISCOVERED_TAG": {
                "value": "ZBXdiscovered",
                "descr": "Name of Lambda Tag that specifies the function is discovered in Zabbix"
            }
        })
        cfg_checks(py_configs)
        lines = [f'{cfg}="{val}" # {descr}\n' for cfg,val,descr in cfg2tup(py_configs)]
        # add dictionary for selection of AWS Metric/statistic pairs
        lines += [f'AWS_METRIC_SELECT= {str(metsel)} # which statistics to select from which metrics']
        for f in PY_CONFIG_FILES:
            with open(f,"w") as fi:
                fi.writelines(lines)

    print("\nCreating AWS SAM template parameters JSON file for zblamb-sam/sam.py script")
    print()
    if update_config(sam_parameters):
        cfg_checks(sam_parameters)
        zblamb_metrics = ','.join([met for met in metsel])
        lines = {
            cfg: val
            for cfg,val,_ in cfg2tup(sam_parameters) if val
        }
        lines.update({"ZBLambMetrics":zblamb_metrics})
        lines.update({"ZBLambZabbixSuffix":py_configs["ZBX_SUFFIX"]["value"]})
        with open("zblamb-sam/template_params.json", "w") as f:
            json.dump(lines,f,indent=2)

    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--env":
        if update_config(docker_env):
            # Docker compose .env file
            docker_env.update(
                {
                    "ZBX_SERVER_HOST": { "value": "zabbix-server", "descr":""},
                    "POSTGRES_USER": { "value": "pg-user", "descr":""},
                    "POSTGRES_PASSWORD": { "value": "pg-pwd", "descr":""},
                    "POSTGRES_DB": { "value": "zabbix", "descr":""},
                    "ZBX_SUFFIX": {"value": py_configs["ZBX_SUFFIX"]["value"], "descr":""}
                }
            )
            lines = [f"{cfg}={val}\n" for cfg,val,_ in cfg2tup(docker_env)]
            with open("compose/.env", "w") as f:
                f.writelines(lines)

    from shutil import copy
    copy("./metrics_def.py", "./scripts/")
    
    print("Done!")