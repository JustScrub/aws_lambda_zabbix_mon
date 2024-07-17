import sys
import itertools
from pyzabbix import ZabbixAPI, ZabbixAPIException


class LLDMetricConfg:
    def __init__(self, name, type, const_map, severity_map, trigger_exp, const_name=None):
        """
        :param: name:str = name for the metric,
        :param: trigger_exp:str = zabbix trigger expression where 
                            the server is replaced by {0} 
                            and relevant constant by {1} 
                            - they will be added in a create function 

                            - e.g. `'last({0})>{1}'`, `'count({0},5m,"ge","{1}")>=1'`,

        :param: zabbix_value_type:int = value type of the metric - read zabbix API for codes,
        :param: const_mapping:[int] = list of constants to map lambda priorities to (lambda priorities are indexes), 
        :param: severity_mapping:[int] = list of zabbix severity codes (0-5) to map lambda priorities to (indexes as well)
        :param: const_name:str = optional name for constants associated with this metric, default uppercase name
        """
        self.name=name
        try:
            self.type = {
                "float":0,float:0,
                "int":3,int:3,
                "char":1,
                "log":2,
                "text":4
            }[type]
        except: raise ValueError(f"Invalid metric type: {type}")

        if len(const_map) != len(severity_map): raise ValueError("Mappings have different length")
        self.consts, self.sevs = const_map, severity_map
        self.expr=trigger_exp
        self.const = const_name or name.upper()

    def item_key(self,suffix,name_tag):
        return f"{self.name}.metrics.{suffix}[{{#{name_tag}}}]"
    
    def trigger_name(self,suffix,name_tag):
        return f"{self.name}.triggers.{suffix}[{{#{name_tag}}}]"

    def expression(self,suffix,name_tag,prio_tag,zabbix_host=None):
        zabbix_host = zabbix_host or suffix
        return self.expr.format(
                f"/{zabbix_host}/{self.item_key(suffix,name_tag)}",
                "{$%s:\\\"{#%s}\\\"}" % (self.const, prio_tag) # f-string: {{${self.const}:{{#{prio_tag}}}}} -- is this LISP??
            )


def create_lambda_discovery_host(
        zapi, 
        metrics, 
        suffix="lambda.zblamb", 
        prio_tag="PRIO", 
        name_tag="FN_NAME",
        group_id=None,
        host_id=None):
    """
    :param: zapi ZabbixAPI instance
    :param: suffix Suffix to use for lambda discovery objects
    :param: metrics list of MetricConfig
    :param: group_id Zabbix ID of the group to add the host to
    :param: host_id Zabbix ID of the host to add discovery to.
    """

    # create host
    group_id = group_id or zapi.hostgroup.create(
        name=f"group.{suffix}"
    )["groupids"][0]

    trapper_host_id = host_id or zapi.host.create(
        host=suffix,
        groups=[{"groupid":group_id}]
    )["hostids"][0]

    # create LLD rule
    discovery_item_id=zapi.discoveryrule.create(
        name="Discover Lambda Functions",
        key_=f"discover.{suffix}",
        hostid=f"{trapper_host_id}",
        type=2 # trapper
    )["itemids"][0]
        
    # generator of "step" field of overrides
    step_g = itertools.count(start=1)
    
    # configure objects per-metric
    for metric in metrics:
        # create user macros with context -- maps lambda priorities to trigger constants (when the trigger triggers)
        #                                 -- for each metric and possible lambda priority
        macros=[
            {
                "hostid": f"{trapper_host_id}",
                "macro": f'{{${metric.const}:{i}}}', # who came up with this macro naming convention ffs??
                "value": f"{v}"
            }
        for i,v in enumerate(metric.consts)
        ]
        zapi.usermacro.create(*macros)
        
        # create item prototypes -- discovered items for each lambda, each lambda tracks each metric
        zapi.itemprototype.create(
            name=f"{{#{name_tag}}} {metric.name} item",
            key_=metric.item_key(suffix,name_tag),
            hostid=f"{trapper_host_id}",
            ruleid=f"{discovery_item_id}",
            type=2, # trapper
            value_type=metric.type
        )

        # create trigger prototypes -- for each discovered item (lambda), one trigger per metric
        #                           -- parametrized with constants (macros) and severities (overrides) for each lambda
        zapi.triggerprototype.create(
            description=metric.trigger_name(suffix,name_tag),
            expression=metric.expression(suffix,name_tag,prio_tag)
        )

    # add overrides to LLD rules -- maps lambda priorities to zabbix severity (how severe a trigger is)
    #                            -- one for each priority, each updates severity for every metric trigger
    zapi.discoveryrule.update(
        itemid=f"{discovery_item_id}",
        overrides=[
            {
                "name": f"OV_PRIO_{i}",
                "step": f"{next(step_g)}",
                "stop": 1, # stop if filter matches -- this override updates all triggers (of all metrics)
                "filter": {
                    "evaltype": "2",
                    "conditions": [
                        {
                            "macro": f"{{#{prio_tag}}}",
                            "operator": "8",
                            "value": f"^{i}$"
                        }
                    ]
                },
                "operations": [
                    {
                        "operationobject": "1", # trigger
                        "value": metric.trigger_name(suffix,name_tag),
                        "opseverity": {"severity": metric.sevs[i]}
                    }
                    for metric in metrics
                ]
            }
        for i in range(len(metrics[0].sevs)) # iterate over all priorities
        ]
    )

    return trapper_host_id





if __name__ == "__main__":

    frontend_host=sys.argv[1] if len(sys.argv)>1 else "localhost"
    frontend_port=sys.argv[2] if len(sys.argv)>2 else 80
    try:
        frontend_port=int(frontend_port)
    except:
        print("Invalid frontend port: must be number!")
        exit(1)
    url=f"http://{frontend_host}:{frontend_port}"


    zapi = ZabbixAPI(url)
    zapi.login("Admin", "zabbix")
    
    metrics = [
        LLDMetricConfg(
            "errors", int,
            const_map=[1, 2, 1, 1, 2, 2, 3, 3, 3, 4, 1],
            severity_map=[5, 5, 4, 4, 4, 3, 3, 2, 2, 1, 0],
            trigger_exp='count({0},5m,"ge","{1}")>=1'
        )
    ]

    create_lambda_discovery_host(zapi, metrics, group_id=21)