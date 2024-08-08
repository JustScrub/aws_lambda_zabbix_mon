import sys, os, json

DRY=False
DEFAULT_TEMPLATE='./templates/metric-stream.yaml'
SAMCONFIG='samconfig.yaml'
HANDLER_DIR = './functions/basic_handler/'
BUILT_TEMPLATE='./.aws-sam/build/template.yaml'

param_in_templates = {
  "ZBLambDummyDeliveryStreamBucket":["metric-stream"],
  "ZBLambTransformBufferingSeconds":["metric-stream"],
  "ZBLambTransformBufferingMegabytes":["metric-stream"],
  "ZBLambMetrics":["metric-stream"],
  "ZBLambCreateMockLambda":["metric-stream"],
  "ZBLambTransformTimeout":["metric-stream"],
  "ZBLambZabbixIP":["metric-stream"],
  "ZBLambVPC":[ "zbx_server_proxy"],
  "ZBLambPrivSubnet":["metric-stream", "zbx_server_proxy"],
  "ZBLambPubSubnet":[ "zbx_server_proxy"],
  "ZBLambSSHRange":[ "zbx_server_proxy"],
  "ZBLambHTTPRange":[ "zbx_server_proxy"],
  "ZBLambZBXPortRange":[ "zbx_server_proxy"],
  "ZBLambInstanceType":[ "zbx_server_proxy"],
  "ZBLambImage":[ "zbx_server_proxy"],
  "ZBLambDBUser":[ "zbx_server_proxy"],
  "ZBLambDBPwd":[ "zbx_server_proxy"],
  "ZBLambCreditSpec":[ "zbx_server_proxy"],
  "ZBLambCreateProxy":[ "zbx_server_proxy"]
}

def dict2arg_list(params):
    return " ".join([f"{k}={v}" for k,v in params.items()])

def get_template(args):
    if "--template" in args:
        return args[args.index('--template')+1]
    elif "-t" in args:
        return args[args.index('-t')+1]
    else:
        return None

def filter_template_params(template, params):
    for t in ["metric-stream", "zbx_server_proxy"]:
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
    template = get_template(args)
    t_arg = ""
    if template is None:
        template = DEFAULT_TEMPLATE
        t_arg = f"-t {template}"
    params = filter_template_params(template,params)
    param_list = dict2arg_list(params)
    call = f"sam {sys.argv[1]} {args} {t_arg} --config-file {SAMCONFIG} --parameter-overrides {param_list}"

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

    