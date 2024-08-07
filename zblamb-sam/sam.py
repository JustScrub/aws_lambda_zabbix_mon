import sys, os, shutil, json

DRY=False
TEMPLATE='./metric-stream.yaml'
SAMCONFIG='samconfig.yaml'
HANDLER_DIR = './functions/basic_handler/'
BUILT_TEMPLATE='./.aws-sam/build/template.yaml'


def dict2arg_list(params):
    return " ".join([f"{k}={v}" for k,v in params.items()])

BUILD_COPY_FILES = ['utils.py', 'requirements.txt', 'config.py', 'metric_map.json']
def build(params, args):
    param_list = dict2arg_list(params)
    call = f"sam build -t {TEMPLATE} --config-file {SAMCONFIG} --parameter-overrides {param_list} {args}"
    

    for file in BUILD_COPY_FILES:
        shutil.copy(f"./functions/utils/{file}",HANDLER_DIR)

    print("calling:\n"+call)
    c=0
    if not DRY:
        c = os.system(call)

    for file in BUILD_COPY_FILES:
        os.remove(f"{HANDLER_DIR}{file}")

    return c

def default_cmd(params,args):
    param_list = dict2arg_list(params)
    call = f"sam {sys.argv[1]} --config-file {SAMCONFIG} --parameter-overrides {param_list} {args}"

    print("calling:\n"+call)
    c=0
    if not DRY:
        c= os.system(call)
    return c



def print_usage():
    print("usage: python3 sam.py <command> <path_to_template_parameters.json> [other AWS SAM CLI args]")
    print("<command>: AWS SAM CLI command")
    print("for build, template is 'metric-stream.yaml'")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_usage()
        exit(1)

    cmd = sys.argv[1]

    with open(sys.argv[2]) as parf:
        params = json.load(parf)

    args = " ".join(sys.argv[3:])
    exit( globals().get(cmd,default_cmd)(params,args) )

    