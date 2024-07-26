#!/bin/python3
import json, socket, random, struct, sys
import time

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
        "host":"multi.lambda.zblamb",
        "key": "errors.metrics.multi.lambda.zblamb[La]",
        "value":random.randint(*vs),
        "clock": (time.time_ns()//1_000_000_000)-(10*60),
        "ns": time.time_ns()%1_000_000_000      # a bit off but who cares
        }
    for _ in range(ireps)],
    "clock": time.time_ns()//1_000_000_000,
    "ns": time.time_ns()%1_000_000_000      
}).encode("utf-8") for _ in range(oreps)]

for m in M:
    s=socket.create_connection(("127.0.0.1",10051))
    s.sendall(b"ZBXD\1" + struct.pack("<II",len(m),0) + m)
    print(s.recv(1024))
    s.close()