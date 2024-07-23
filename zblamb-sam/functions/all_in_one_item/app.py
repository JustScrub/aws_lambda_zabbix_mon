import json, struct, socket, base64, os, itertools as i

def lambda_handler(e,c):
    print(e)
    #return {'records': [{'recordId': r['recordId'],'result': 'Dropped','data': ''} for r in R]}

    firehose_data= e['records'] # a list of firehose records
    firehose_data= [ base64.b64decode(r['data']).decode('utf-8') for r in firehose_data ] # only take the 'data' parameter of the record and decode it from base64
    firehose_data= i.chain(*[data.splitlines() for data in firehose_data]) # decoded data contains json files separated by newlines -- chain all json files into a flat list
    firehose_data= map(json.loads, firehose_data) # convert the string jsons to python dictionaries and lists
    firehose_data= filter( 
        lambda json: list(json['dimensions'].keys())==['FunctionName'],
        firehose_data  ) # only keep those jsons, where the 'dimensions' parameter object has only the 'FunctionName' parameter
    # one-liner: 
    # firehose_data= i.chain(*[ list(filter(lambda j: list(j['dimensions'].keys())==['FunctionName'],map( json.loads,base64.b64decode(r['data']).decode('utf-8').splitlines() )))  for r in e['records']])
    
    zabbix_host = "errors.all-in-one.lambda.zblamb"
    for j in firehose_data:
        Value, FunctionName = int(j['value']['sum']), j['dimensions']['FunctionName']
        d = json.dumps(
            {
                "request":"sender data",  # zabbix_sender request to zabbix server -- only trapper items are used
                "data": 
                [
                    *([ 
                        { 
                            "host":zabbix_host,
                            "key":"error-stream",
                            "value":FunctionName } 
                      ] * Value), # error-stream: for each error, sends name of the failed function
                    {
                        "host":zabbix_host,
                        "key":"error-log",
                        "value":f"ERROR {Value} {FunctionName}"
                    }, # logs number of errors for a function
                    {
                        "host":zabbix_host,
                        "key":"error-counts",
                        "value":f"{Value}"
                    }, # just sends number of failures, without lambda name
                    {
                        "host":zabbix_host,
                        "key":"error-count-string",
                        "value":','.join([FunctionName]*Value)
                    } # "unary"-base number of failures, "digits" are name of the function and are separated by a comma
                      # e.g. 'Lambda1,Lambda1,Lambda1' -- the function 'Lambda1' failed 3 times
                ],
                "clock":j['timestamp'] 
            }
        ).encode("utf-8") # encode to bytes object for socket
        #s=socket.create_connection((os.env['ZBLAMB_PROXY_IP'],10051))
        #s.sendall(b"ZBXD\1" + struct.pack("<II",len(d),0) + d)
        #print(s.recv(1024))
        #s.close()
        print(b"ZBXD\1" + struct.pack("<II",len(d),0) + d)
    return {'records': [{'recordId': r['recordId'],'result': 'Dropped','data': ''} for r in e['records']]} # drop all data, do not send it further via firehose