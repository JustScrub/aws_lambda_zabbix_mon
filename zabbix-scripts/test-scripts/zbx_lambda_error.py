#!/bin/python

import sys, socket, struct, json

#simulate Lambda error

if len(sys.argv) < 3:
    print("usage: python zbx_lambda_error.py <Function_Name>=<error_count> [...]")

def arg2tup(s):
    f,e = s.split('=')
    return (f, int(e))

in_data = list(map(arg2tup, sys.argv[1:]))

for fn,e in in_data:
    d = json.dumps({
        "request": "sender data",
        "data": [
            *([{
                "host": "zblamb-lambda-errors",
                "key": "error-stream",
                "value": fn
            }] * e),
            {
                "host": "zblamb-lambda-errors",
                "key": "error-counts",
                "value": e
            },
            {
                "host": "zblamb-lambda-errors",
                "key": "error-count-string",
                "value": ','.join([fn]*e)
            },
            {
                "host": "zblamb-lambda-errors",
                "key": "error-log",
                "value": f"ERROR {e} {fn}"
            }
        ]
    }).encode("utf-8")

    s=socket.create_connection(("localhost",10051))
    s.sendall(b"ZBXD\1" + struct.pack("<II",len(d),0) + d)
    print(s.recv(1024))
    s.close()