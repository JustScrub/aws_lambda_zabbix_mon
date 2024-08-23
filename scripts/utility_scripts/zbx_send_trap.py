#!/bin/python3
import random, sys, time
from zappix.sender import Sender
from zappix.protocol import SenderData
from ..config import ZBX_SUFFIX


def send_test_trap(zbx_addr,function,metric,rand_range,n_values,time_update_s=0,suffix=ZBX_SUFFIX):
    """
    Send trapper packet to Zabbix host specified by `suffix` containing `n_values` values.
    :param zbx_addr: tuple (zabbix ip or dns, zabbix port) -- server/proxy address
    :param function: name of the Lambda function to which's item the trap will be sent
    :param metric: name of the metric to send the value to
    :param rand_range: tuple (min,max) -- range for random int generator (both included)
    :param n_values: number of values inside each packet
    :param time_update_s: relative time shift of value record, in seconds. Zabbix will put the value on time-axis at point `now + time_update_s`
    :param suffix: suffix of Zabbix objects (host=`suffix`, item=`<metric>.metrics.<suffix>[<function>]`)
    """

    M = [SenderData(
            **{
            "host":suffix,
            "key": f"{metric}.metrics.{suffix}[{function}]",
            "value":random.randint(*rand_range),
            "clock": (time.time_ns()//1_000_000_000)+(time_update_s),
            "ns": time.time_ns()%1_000_000_000      # a bit off but who cares
            }
        )
        for _ in range(n_values)]

    s=Sender(*zbx_addr)
    s.set_timeout(3)
    resp = s.send_bulk(M,True)
    return resp

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 -m scripts.utility_scripts.zbx_send_trap FnName [n_values=3] [low:high=0:100] [metric=sum.errors] [server_addr=localhost]")
        print("FnName: name of the discovered function -- Zabbix item metric.metrics.<suffix>.[FnName]")
        print("\t<suffix> is taken from config")
        print("n_values: number of values in each packet")
        print("low:high: low and high boundaries of range of random value to send")
        print("\t(e.g. 1:5 sends random value between 1 and 5 including both; 3:3 always sends 3)")
        print("metric: the metric of the discovered function -- Zabbix item metric.metrics.<suffix>.[FnName], includes statistic and metric names")
        print("server_addr: IP address or DNS name of a Zabbix Server/Proxy listening on port 10051")
        exit(1)
    fn = sys.argv[1]    

    try: ireps=int(sys.argv[2])
    except: ireps=3

    try: vs = tuple(map(int,sys.argv[3].split(':')))[:2]
    except: vs = (0,100)

    try: metric = sys.argv[4]
    except: metric = "sum.errors"

    try: servaddr = sys.argv[5]
    except: servaddr = 'localhost'
    
    print(f"using range {vs}")

    print(
        send_test_trap(
            (servaddr,10051),
            function=fn,
            metric=metric,
            rand_range=vs,
            n_values=ireps,
            time_update_s=0, # -10*60 # 10 minutes ago
            suffix=ZBX_SUFFIX
        )
    )