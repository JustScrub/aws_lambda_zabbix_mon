#!/bin/python
import json
from zappix.sender import Sender
from ..config import ZBX_SUFFIX,ZBX_PRIO_MACRO,ZBX_FN_NAME_MACRO


def parse_lines(lines):
    discoveries = []
    for line in lines:
        l = line.strip().split()
        print(l)
        discoveries.append({ f"{{#{ZBX_FN_NAME_MACRO}}}": l[0],})
        discoveries[-1].update(
            {
                f"{{#{metric.upper()}_{ZBX_PRIO_MACRO}}}": prio
                for prio_pair in l[1:]
                for metric,prio in [prio_pair.split(':')]
            }
        )
    return discoveries

def auto_discover(discovery_lines, zab_addr, suffix=ZBX_SUFFIX):
    discovered = parse_lines(discovery_lines)
    print(discovered)
    s = Sender(*zab_addr)
    resp = s.send_value(suffix,f"discover.{suffix}",json.dumps(discovered))
    return resp

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python3 -m scripts.utility_scripts.zbx_auto_discover <path> [zabbix_host]")
        print("path: path to file containing functions to discover, or dash (-) to read from stdin")
        print("\tthe format is: <FunctionName> <metric>:<priority> ...")
        print("\tFunctionName is the name of the function to discover")
        print("\tmetric and priority are name of the metric and the function's priority for the metric")
        print("\tmore <metric>:<priority> pairs can be specified, metrics should not repeat")
        print("zabbix_host: IP address or DNS name of Zabbix Server/Proxy to push data to. Default 'localhost'. Port must be 10051")
        exit(1)

    if sys.argv[1] != '-':
        with open(sys.argv[1]) as f:
            lines = f.readlines()
    else: lines = sys.stdin.readlines()

    
    addr = (sys.argv[2] if len(sys.argv) > 2 else"localhost", 10051)
    suffix = ZBX_SUFFIX

    print(
        auto_discover(lines,addr,suffix)
    )
