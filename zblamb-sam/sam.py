import sys, os, json

DRY=False
DEFAULT_TEMPLATE='metric-stream.yaml'
SAMCONFIG='samconfig.yaml' # relative to template path, all templates in ./templates/ dir
HANDLER_DIR = './functions/basic_handler/'
BUILT_TEMPLATE='./.aws-sam/build/template.yaml'

param_in_templates = {
  "ZBLambDummyDeliveryStreamBucket":["metric-stream", "demo"],
  "ZBLambTransformBufferingSeconds":["metric-stream"],
  "ZBLambTransformBufferingMegabytes":["metric-stream"],
  "ZBLambTransformationLambdaRetries":["metric-stream"],
  "ZBLambMetrics":["metric-stream", "demo"],
  "ZBLambDiscoveryRate":["metric-stream", "demo"],
  "ZBLambCreateMockLambda":["metric-stream", "demo"],
  "ZBLambLambdaTimeout":["metric-stream"],
  "ZBLambZabbixIP":["metric-stream"],
  "ZBLambLambdasInVPC":["metric-stream"],
  "ZBLambVPC":[ "zbx_server_proxy", "demo", "metric-stream"],
  "ZBLambPrivSubnet":["metric-stream", "zbx_server_proxy", "demo"],
  "ZBLambPubSubnet":[ "zbx_server_proxy", "demo"],
  "ZBLambSSHRange":[ "zbx_server_proxy"],
  "ZBLambHTTPRange":[ "zbx_server_proxy"],
  "ZBLambZBXPortRange":[ "zbx_server_proxy", "metric-stream"],
  "ZBLambInstanceType":[ "zbx_server_proxy"],
  "ZBLambImage":[ "zbx_server_proxy"],
  "ZBLambDBUser":[ "zbx_server_proxy"],
  "ZBLambDBPwd":[ "zbx_server_proxy"],
  "ZBLambZabbixSuffix":["zbx_server_proxy", "demo"],
  "ZBLambCreditSpec":[ "zbx_server_proxy"],
  "ZBLambCreateProxy":[ "zbx_server_proxy", "demo"],
  "DemoCreateNetwork": ["demo"],
}

def dict2arg_list(params):
    return " ".join([f"{k}={v}" for k,v in params.items()])

def get_template():
    args = sys.argv
    if "--template" in args:
        return args[args.index('--template')+1]
    elif "-t" in args:
        return args[args.index('-t')+1]
    else:
        return None

def filter_template_params(template, params):
    for t in ["metric-stream", "zbx_server_proxy", "demo"]:
        if t in template:
            template = t
            break

    params = {
        k: v
        for k,v in params.items()
        if template in param_in_templates[k]
    }
    return params

def default_cmd(params,args):
    template = get_template()
    t_arg = ""
    if template is None:
        template = DEFAULT_TEMPLATE
        t_arg = f"-t {template}"
    print("using template:", template)
    params = filter_template_params(template,params)
    param_list = dict2arg_list(params)
    call = f"sam {sys.argv[1]} {args} {t_arg} --config-file {SAMCONFIG} {'--parameter-overrides' if param_list else ''} {param_list}"

    print("calling:\n"+call)
    c=0
    if not DRY:
        c= os.system(call)
    return c

# deploying requires the built template, which has name "template.yaml" --> must recognize the actual template to pass parameters to
def deploy(params, args):
    template = get_template()
    if template is None:
        with open(BUILT_TEMPLATE, 'r') as tf:
            for line in tf:
                if "TemplateName:" in line:
                    template = line[16:].strip()
                    break

    params = filter_template_params(template,params)
    params = dict2arg_list(params)
    call = f"sam {sys.argv[1]} {args} --config-file {SAMCONFIG} {'--parameter-overrides' if params else ''} {params}"

    print("using template:", template)
    print("calling:\n"+call)
    c=0
    if not DRY:
        c= os.system(call)
    return c

def print_usage():
    print("Call AWS SAM CLI with specified command and arguments, automatically filling in the --config-file argument and --parameter-overrides argument based on a JSON file with template parameters\n")
    print("usage: python3 sam.py <command> [other AWS SAM CLI args] <path_to_template_parameters.json>")
    print("\t<command>: AWS SAM CLI command")
    print("\t\tfor build, template is set to 'metric-stream.yaml'")
    print("\t<path_to_template_parameters.json>: Path to JSON file with mapping of template parameters to values")
    print("\tThe order must be kept!")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_usage()
        exit(1)

    cmd = sys.argv[1]

    with open(sys.argv[-1]) as parf:
        params = json.load(parf)

    args = " ".join(sys.argv[2:-1])
    exit( globals().get(cmd,default_cmd)(params,args) )

    