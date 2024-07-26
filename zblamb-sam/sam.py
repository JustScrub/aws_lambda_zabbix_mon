import sys, os, shutil, json

DRY=False
TEMPLATE='./metric-stream.yaml'
CONFIG='samconfig.yaml'

BUILT_TEMPLATE='./.aws-sam/build/template.yaml'

def dict2arg_list(params):
    return " ".join([f"{k}={v}" for k,v in params.items()])


def build(params, args):
    transform = params['ZBLambTransformationFunction']
    param_list = dict2arg_list(params)
    call = f"sam build -t {TEMPLATE} --config-file {CONFIG} --parameter-overrides {param_list} {args}"
    
    shutil.copy(f"./functions/utils/utils.py",f"./functions/{transform}/")
    shutil.copy(f"./functions/utils/requirements.txt",f"./functions/{transform}/")

    print("calling:\n"+call)
    c=0
    if not DRY:
        c = os.system(call)

    os.remove(f"./functions/{transform}/utils.py")
    os.remove(f"./functions/{transform}/requirements.txt")

    return c

def deploy(params,args):
    param_list = dict2arg_list(params)
    call = f"sam deploy --config-file {CONFIG} --parameter-overrides {param_list} {args}"

    os.system('pwd; ls')
    print("calling:\n"+call)
    c=0
    if not DRY:
        c= os.system(call)
    return c



def print_usage():
    print("usage: python3 sam.py <command> <path_to_template_parameters.json> [other AWS SAM CLI args]")
    print("<command>: one of build, deploy")
    print("for build, template is 'metric-stream.yaml'")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_usage()
        exit(1)

    cmd = sys.argv[1]
    if cmd not in {'deploy', 'build'}:
        print_usage()
        exit(1)

    with open(sys.argv[2]) as parf:
        params = json.load(parf)

    args = " ".join(sys.argv[3:])
    exit( globals()[cmd](params,args) )

    