#!/bin/python3
import json, socket, random, struct, sys
import time
from ..config import ZBX_SUFFIX


def send_error_test_trap(zbx_addr,function,metric,rand_range,n_values,n_packets,time_update_s=0,suffix=ZBX_SUFFIX):
    """
    Send `oreps` trapper packets to Zabbix host specified by `suffix`, each packet containing `ireps` values.
    :param zbx_addr: tuple (zabbix ip or dns, zabbix port) -- server/proxy address
    :param function: name of the Lambda function to which's item the trap will be sent
    :param metric: name of the metric to send the value to
    :param rand_range: tuple (min,max) -- range for random int generator (both included)
    :param ireps: number of values inside each packet
    :param oreps: number of packets
    :param time_update_s: relative time shift of value record, in seconds. Zabbix will put the value on time-axis at point `now + time_update_s`
    :param suffix: suffix of Zabbix objects (host=`suffix`, item=`<metric>.metrics.<suffix>[<function>]`)
    """

    M = [json.dumps({
        "request": "sender data",
        "data": [
            {
            "host":suffix,
            "key": f"{metric}.metrics.{suffix}[{function}]",
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
    if len(sys.argv) < 2:
        print("Usage: python3 -m scripts.utility_scripts.zbx_send_trap FnName [n_packets=10] [n_values=3] [low:high=0:100] [metric=errors]")
        print("FnName: name of the discovered function -- Zabbix item metric.metrics.<suffix>.[FnName]")
        print("\t<suffix> is taken from config")
        print("n_packets: number of packets to send")
        print("n_values: number of values in each packet")
        print("low:high: low and high boundaries of range of random value to send")
        print("\t(e.g. 1:5 sends random value between 1 and 5 including both; 3:3 always sends 3)")
        print("metric: the metric of the discovered function -- Zabbix item metric.metrics.<suffix>.[FnName]")
        exit(1)
    fn = sys.argv[1]
    try:
        oreps=int(sys.argv[2])
    except:
        oreps=10    
    try:
        ireps=int(sys.argv[3])
    except:
        ireps=3

    try:
        vs = tuple(map(int,sys.argv[4].split(':')))[:2]
    except:
        vs = (0,100)
    try:
        metric = sys.argv[5]
    except:
        metric = "errors"
    
    print(f"using range {vs}")

    print(
        send_error_test_trap(
            ('localhost',10051),
            function=fn,
            metric=metric,
            rand_range=vs,
            n_values=ireps,
            n_packets=oreps,
            time_update_s=0, # -10*60 # 10 minutes ago
            suffix=ZBX_SUFFIX
        )
    )