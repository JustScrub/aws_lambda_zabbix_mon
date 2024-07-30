
py_configs = {
    "ZBX_SUFFIX":{
		"value":'zblamb',
		"descr":'Zabbix objects base/root name'},
    "AWS_PRIO_TAG":{
		"value":'PRIO',
		"descr":'Name of Lambda Functions Tag that yields the function\'s priority'},
    "ZBX_PRIO_MACRO":{
		"value":'PRIO',
		"descr":'Zabbix LLD Macro that yields the discovered function priority'},
    "ZBX_FN_NAME_MACRO":{
		"value":'FN_NAME',
		"descr":'Zabbix LLD Macro that yields the discovered function name'},
    "ZBX_MONITORED_TAG":{
		"value":'ZabbixMonitored',
		"descr":'Name of Lambda Function Tag that stores whether the function is already discovered'},
}
PY_CONFIG_FILES = [
        "scripts/config/__init__.py",
        "zblamb-sam/functions/utils/config.py"
        ]

sam_parameters = {
  "ZBLambDummyDeliveryStreamBucket":{
		"value":'',
		"descr":"A dummy S3 bucket ARN. The bucket will not be handelded with, it's just because of requirements."},
  "ZBLambVPC":{
		"value":'',
		"descr":'The VPC ID under which to run EC2 instances.'},
  "ZBLambPrivSubnet":{
		"value":'',
		"descr":'A private subnet ID. Must belong to ZBLambVPC.'},
  "ZBLambPubSubnet":{
		"value":'',
		"descr":'A public subnet ID. Must belong to ZBLambVPC.\nIf you have a way to connect to a VPC instance other than public IP (e.g. VPN), you may specify ID of a private subnet in ZBLambVPC.'},
  "ZBLambSSHRange":{
		"value":'0.0.0.0/0',
		"descr":'CIDR range of IP addresses able to connect via SSH'},
  "ZBLambHTTPRange":{
		"value":'0.0.0.0/0',
		"descr":'CIDR range of IP addresses able to connect to ports 80, 8080, 443 and 8443'},
  "ZBLambZBXPortRange":{
		"value":'0.0.0.0/0',
		"descr":'CIDR range of IP addresses able to connect to Zabbix ports 10050 and 10051. Recommended the range of specified VPC.'},
  "ZBLambInstanceType":{
		"value":'t3a.micro',
		"descr":'Type of EC2 instances.'},
  "ZBLambImage":{
		"value":'ami-04f1b917806393faa',
		"descr":'Image of EC2 instances'},
  "ZBLambDBUser":{
		"value":'zabbix',
		"descr":'Zabbix DB user'},
  "ZBLambDBPwd":{
		"value":'zabbix',
		"descr":'Zabbix DB user password'},
#  "ZBLambCreditSpec":{
#		"value":'standard',
#		"descr":''},
}

def update_config(cfg_dict):
    for k in cfg_dict:
        try:
            print(cfg_dict[k]['descr'])
            cfg_dict[k]['value'] = input(f"{k} ({cfg_dict[k]['value']}): ") or cfg_dict[k]['value']
            print()
        except KeyboardInterrupt:
            return False
    return True

def cfg2dict(cfg_dict):
    return map(lambda e: (e[0],e[1]['value'],e[1]['descr']), cfg_dict.items())


def metric_map():
    from .metrics_def import MetricConfigs
    if len( set(type(metric) for metric in MetricConfigs) ) != 1:
        print("Metrics in metrics_def.py MetricConfigs must be of one type and the list cannot be empty!")
        exit(1)

    json_dict = {}
    for metric in MetricConfigs:
        if metric.aws_metric not in json_dict:
            json_dict[metric.aws_metric] = {
                metric.aws_stat: [metric.name]
            }
            continue

        if metric.aws_stat not in json_dict[metric.aws_metric]:
            json_dict[metric.aws_metric][metric.aws_stat] = [metric.name]
            continue

        json_dict[metric.aws_metric][metric.aws_stat].append( metric.name )
    
    return json_dict
        

import json
if __name__ == "__main__":
    metmap = metric_map()
    print("Python scripts and AWS SAM template parameters config.")
    print("To cancel filling out a config, press CTRL+C - this will not write the config")
    input("Press enter to continue")

    print("Configuring python scripts\n")
    if update_config(py_configs):
        lines = [f'{cfg}="{val}" # {descr}\n' for cfg,val,descr in cfg2dict(py_configs)]
        for f in PY_CONFIG_FILES:
            with open(f,"w") as fi:
                fi.writelines(lines)

    print("Creating AWS SAM template parameters JSON file for zblamb-sam/sam.py script")
    print("By leaving parameters empty, running sam.py later will prompt you to fill them in")
    if update_config(sam_parameters):
        zblamb_metrics = ','.join([met for met in metmap])
        lines = {
            cfg: val
            for cfg,val,_ in cfg2dict(sam_parameters) if val
        }
        lines.update({"ZBLambMetrics":zblamb_metrics})
        with open("zblamb-sam/template_params.json", "w") as f:
            json.dump(lines,f,indent=2)

    with open("zblamb-sam/functions/utils/metric_map.json", "w") as f:
        json.dump(metmap,f,indent=2)
    
    print("Done!")