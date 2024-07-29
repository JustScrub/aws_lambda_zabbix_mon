from pyzabbix import ZabbixAPI
from utility_scripts import auto_discover
from zapi import LambdaPriority
import boto3
import json, sys, os
from config import ZBX_SUFFIX, AWS_PRIO_TAG

def zbx_delete_triggers(zapi,function_name,suffix=ZBX_SUFFIX):
    # get the trigger IDs
    ids = [ res['triggerid']
        for res in zapi.trigger.get(
            search={
                "description": f"triggers.{suffix}[{function_name}]"
            },
            output=['triggerid']
    )]

    if ids:
        ids = zapi.trigger.delete(*ids)['triggerids']

    return ids

def aws_lambda_set_prio_tag(lambda_client,function_name,prio:LambdaPriority):
    fn_arn = lambda_client.get_function(FunctionName=function_name)['Configuration']['FunctionArn']
    lambda_client.tag_resource(
        Resource=fn_arn,
        Tags={
            AWS_PRIO_TAG: f"{prio.value}"
        }
    )

def update_priority(zab_addr,function_name,priority:LambdaPriority):
    zapi = ZabbixAPI(f"http://{zab_addr[0]}:{zab_addr[1]}")
    lambda_client = boto3.client('lambda')

    zbx_delete_triggers(zapi,function_name,ZBX_SUFFIX)
    aws_lambda_set_prio_tag(lambda_client,function_name,priority)
    auto_discover([(function_name,priority.value)],zab_addr,ZBX_SUFFIX)


if __name__=="__main__":

    if len(sys.argv) < 3:
        print("usage: python3 lambda_update_priority <function_name> <priority> [<frontend_host>=localhost] [<frontend_port>=80]")
        print("<function_name>: name of the AWS Lambda function")
        print("<priority>: new valid priority number for the function")
        print("<frontend_host>, <frontend_port>: IP or DNS name and port of the Zabbix Frontend")
        exit(1)

    function_name = sys.argv[1]
    priority = sys.argv[2]
    frontend_host=sys.argv[3] if len(sys.argv)>3 else os.environ.get("ZBLAMB_FRONTEND_HNAME","localhost")
    frontend_port=sys.argv[4] if len(sys.argv)>4 else 80

    try:
        priority=LambdaPriority(int(priority))
    except:
        print("Invalid priority: must be number in Lambda priority range!")
        exit(1)

    try:
        frontend_port=int(frontend_port)
    except:
        print("Invalid frontend port: must be number!")
        exit(1)
    zab_addr = (frontend_host,frontend_port)

    update_priority(zab_addr,function_name,priority)