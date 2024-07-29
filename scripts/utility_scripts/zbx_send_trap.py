#!/bin/python3
import json, socket, random, struct, sys
import time
from ..config import ZBX_SUFFIX


def send_error_test_trap(zbx_addr,function,rand_range,n_values,n_packets,time_update_s=0,suffix=ZBX_SUFFIX):
    """
    Send `oreps` trapper packets to Zabbix host specified by `suffix`, each packet containing `ireps` values.
    :param zbx_addr: tuple (zabbix ip or dns, zabbix port) -- server/proxy address
    :param function: name of the Lambda function to which's item the trap will be sent
    :param rand_range: tuple (min,max) -- range for random int generator (both included)
    :param ireps: number of values inside each packet
    :param oreps: number of packets
    :param time_update_s: relative time shift of value record, in seconds. Zabbix will put the value on time-axis at point `now + time_update_s`
    :param suffix: suffix of Zabbix objects (host=`suffix`, item=`errors.metrics.<suffix>[<function>]`)
    """

    M = [json.dumps({
        "request": "sender data",
        "data": [
            {
            "host":suffix,
            "key": f"errors.metrics.{suffix}[{function}]",
            "value":random.randint(*rand_range),
            "clock": (time.time_ns()//1_000_000_000)+(time_update_s),
            "ns": time.time_ns()%1_000_000_000      # a bit off but who cares
            }
        for _ in range(n_values)],
        "clock": time.time_ns()//1_000_000_000,
        "ns": time.time_ns()%1_000_000_000      
    }).encode("utf-8") for _ in range(n_packets)]

    resp = []
    for m in M:
        s=socket.create_connection(zbx_addr)
        s.sendall(b"ZBXD\1" + struct.pack("<II",len(m),0) + m)
        resp.append(s.recv(1024))
        s.close()

    return resp

if __name__ == "__main__":
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

    send_error_test_trap(
        ('localhost',10051),
        function="Lz",
        rand_range=vs,
        n_values=ireps,
        n_packets=oreps,
        time_update_s=0, # -10*60 # 10 minutes ago
        suffix=ZBX_SUFFIX
    )