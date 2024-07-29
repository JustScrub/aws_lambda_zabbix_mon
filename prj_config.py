
py_configs = {
    "ZBX_SUFFIX":{
		"value":'multi.lambda.zblamb',
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
# "ZBLambTransformationFunction":{
#		"value":'',
#		"descr":'Transformation Function. '},
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
        print(cfg_dict[k]['descr'])
        cfg_dict[k]['value'] = input(f"{k} ({cfg_dict[k]['value']}): ") or cfg_dict[k]['value']
        print()

def cfg2dict(cfg_dict):
    return map(lambda e: (e[0],e[1]['value'],e[1]['descr']), cfg_dict.items())

if __name__ == "__main__":
    print("Configuring python scripts\n")
    update_config(py_configs)
    lines = [f'{cfg}="{val}" # {descr}\n' for cfg,val,descr in cfg2dict(py_configs)]

    for f in PY_CONFIG_FILES:
        with open(f,"w") as fi:
            fi.writelines(lines)

    print("Creating AWS SAM template parameters JSON file for zblamb-sam/sam.py script")
    print("By leaving parameters empty, running sam.py later will prompt you to fill them in")
    update_config(sam_parameters)
    lines = '{\n' + ',\n'.join([f'\t"{cfg}": "{val}"' for cfg,val,_ in cfg2dict(sam_parameters) if val]) + '\n}'

    with open("zblamb-sam/template_params.json", "w") as f:
        f.write(lines)

    
