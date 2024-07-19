#!/bin/python
import socket, struct, sys, json

if len(sys.argv) < 2:
    print(f"Usage: python zbx_auto_discover.py FnName,Priority [...]")
    print("FnName: Name of Lambda Function")
    print("Priority: its priority")

discovered = [{"{#FN_NAME}": f, "{#PRIO}":p} for f,p in map(lambda arg: arg.split(','), sys.argv[1:])]

d = json.dumps({
    "request": "sender data",
    "data": [
        {
            "host": "multi.lambda.zblamb",
            "key": "discover.multi.lambda.zblamb",
            "value": json.dumps(discovered)
        }
    ]
}).encode("utf-8")

print(d)
s=socket.create_connection(("localhost",10051))
s.sendall(b"ZBXD\1" + struct.pack("<II",len(d),0) + d)
print(s.recv(1024))
s.close()