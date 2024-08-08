#!/bin/python
import json
from zappix.sender import Sender
from ..config import ZBX_SUFFIX,ZBX_PRIO_MACRO,ZBX_FN_NAME_MACRO


def auto_discover(name_prio_tuples, zab_addr, suffix=ZBX_SUFFIX):
    discovered = [{f"{{#{ZBX_FN_NAME_MACRO}}}": f, f"{{#{ZBX_PRIO_MACRO}}}":p} for f,p in name_prio_tuples]
    s = Sender(*zab_addr)
    resp = s.send_value(suffix,f"discover.{suffix}",json.dumps(discovered))
    return resp

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python3 -m scripts.utility_scripts.zbx_auto_discover FnName,Priority [...]")
        print("FnName: Name of Lambda Function")
        print("Priority: its priority")
        exit(1)
    
    tups = [(f,p) for f,p in map(lambda arg: arg.split(','), sys.argv[1:])]
    addr = ("localhost", 10051)
    suffix = ZBX_SUFFIX

    print(
        auto_discover(tups,addr,suffix)
    )
