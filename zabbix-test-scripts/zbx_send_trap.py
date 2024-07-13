#!/bin/python3
import json, socket, random, struct, sys

try:
    oreps=int(sys.argv[1])
except:
    oreps=10    
try:
    ireps=int(sys.argv[2])
except:
    ireps=3

try:
    vs = tuple(map(int,sys.argv[3].split(':')))[:2]
except:
    vs = (0,100)
print(f"using range {vs}")

M = [json.dumps({
    "request": "sender data",
    "data": [
        {
        "host":"test-host-no-if",
        "key": "no.if.trapper",
        "value":random.randint(*vs)
        }
    for _ in range(ireps)]
}).encode("utf-8") for _ in range(oreps)]

for m in M:
    s=socket.create_connection(("127.0.0.1",10051))
    s.sendall(b"ZBXD\1" + struct.pack("<II",len(m),0) + m)
    print(s.recv(1024))
    s.close()