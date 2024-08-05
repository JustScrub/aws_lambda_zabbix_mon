import sys, os, json, base64
import random, time, itertools
import math


get_functions_cache_file = '__pycache__/__get_functions_cache__'
def get_functions():
    if os.path.exists(get_functions_cache_file):
        with open(get_functions_cache_file) as f:
            return json.load(f)

    import boto3
    lc = boto3.client('lambda')
    functions =  [
        name
        for page in lc.get_paginator('list_functions').paginate()
        for name in map(lambda fn: fn['FunctionName'], page['Functions'])
    ]

    os.makedirs('__pycache__',exist_ok=True)
    with open(get_functions_cache_file,'w') as f:
        json.dump(functions,f)

    return functions

metrics={
    'Errors': 'Count',
    'Duration': 'ms'
}
function_resources = ['S3 bucket', 'API gateway', None] # None = function name

def generate_metric_stream_data(functions):
    # todo: actually simulate values for diff resources + their sum
    dimensions = list(itertools.chain(
    [
        {
            'FunctionName': fn,
            'Resource': resource or fn
        }
        for fn in functions
        for resource in function_resources
    ], [
        {
            'FunctionName': fn
        }
        for fn in functions
    ], [{}]))

    getval = lambda a,b: float(math.floor(random.uniform(a,b)))

    return [
        {
            "account_id": "0123456789",
            "dimensions": d,
            "metric_name": metric,
            "metric_stream_name": "ZBLamb-MockLambda1-ErrorMetricStream",
            "namespace": "AWS/Lambda",
            "region": "eu-central-1",
            "timestamp": time.time_ns() - random.randrange(24*60*60*1000000000),
            "unit": unit,
            "value": {
                "count": getval(1,10),
                "max": getval(6,10),
                "min": getval(0,5),
                "sum": getval(15,20)
            }
        }
        for d in dimensions
        for metric,unit in metrics.items()
    ]


def generate_events(functions,n_events=None,n_records=None,n_functions=None):
    n_events = n_events or random.randint(1,5)
    n_records = n_records or 10
    n_functions = n_functions or len(functions)

    return [
        {
            "deliveryStreamArn": "arn:aws:firehose:eu-central-1:0123456789:deliverystream/ZBLambMetricStreamFirehose",
            "invocationId": f"{j}",
            "records": [
                {
                    "approximateArrivalTimestamp": time.time_ns(),
                    "data": base64.b64encode('\n'.join(map(
                            json.dumps,
                            generate_metric_stream_data(random.sample(functions,random.randrange(1,n_functions)))
                        )).encode('utf-8')),
                    "recordId": f"{i}"
                }
                for i in range(random.randrange(n_records))
            ],
            "region": "eu-central-1"
        }
        for j in range(n_events)
    ]

def print_usage():
    print("Usage: python3 generate_events.py [n_events] [n_records] [n_functions] [file_prefix]")
    print("n_events: number of events to generate. Default = random between 1 and 5")
    print("n_records: maximum number of records in each event. Default = 10")
    print("n_functions: maximum number of functions to randomly select for each record. Default = number of functions")
    print("file_prefix: prefix of file seqence to store events to. If not provided, events are printed to stdout")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "help":
        print_usage()
        exit(0)

    ns = {
        "n_events": None,
        "n_records": None,
        "n_functions": None
    }

    for i,k in enumerate(ns.keys(),1):
        try:
            ns[k] = int(sys.argv[i])
        except IndexError:
            break
        except ValueError:
            print(f"{k} must be integer. Using default...")

    functions = get_functions()
    events = [json.dumps(evt) for evt in generate_events(functions,**ns)]

    if len(sys.argv < 5):
        for event in events:
            print(event)
            exit(0)

    shift=int(math.log10(ns['n_events']))
    for i,event in enumerate(events):
        with open(f"{sys.argv[4]}_{str(i).zfill(shift)}.json","w") as file:
            json.dump(event,file)