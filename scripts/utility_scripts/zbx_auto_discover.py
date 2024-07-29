#!/bin/python
import socket, struct, json


def auto_discover(name_prio_tuples, zab_addr, suffix):
    discovered = [{"{#FN_NAME}": f, "{#PRIO}":p} for f,p in name_prio_tuples]

    d = json.dumps({
        "request": "sender data",
        "data": [
            {
                "host": f"{suffix}",
                "key": f"discover.{suffix}",
                "value": json.dumps(discovered)
            }
        ]
    }).encode("utf-8")

    s=socket.create_connection(zab_addr)
    s.sendall(b"ZBXD\1" + struct.pack("<II",len(d),0) + d)
    resp = s.recv(1024)
    s.close()
    return resp

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python zbx_auto_discover.py FnName,Priority [...]")
        print("FnName: Name of Lambda Function")
        print("Priority: its priority")
    
    tups = [(f,p) for f,p in map(lambda arg: arg.split(','), sys.argv[1:])]
    addr = ("localhost", 10051)
    suffix = "multi.lambda.zblamb"

    print(
        auto_discover(tups,addr,suffix)
    )
