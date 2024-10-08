from pyzabbix import ZabbixAPI, ZabbixAPIException
from typing import List, Dict, Tuple, Union
from enum import Enum
from scripts.config import N_LAMBDA_PRIORITIES, ZBX_LLD_KEEP_PERIOD
import itertools

zabbix_type_dict = {
    "float":0,float:0,
    "int":3,int:3,
    "char":1,
    "log":2,
    "text":4
}

class ZabbixSeverity(Enum):
    NOT_CLASSIFIED=0
    INFORMATION=1
    WARNING=2
    AVERAGE=3
    HIGH=4
    DISASTER=5 

    def __repr__(self) -> str:
        return f"Zˢ({self.name})"

class LambdaPriority:
    num_priorities=int(N_LAMBDA_PRIORITIES)
    def __init__(self,prio:int):
        if prio < -1 or prio > self.num_priorities:
            raise ValueError(f"Priority must be in range [0,{self.num_priorities}) or -1 for untracked")
        self.value = prio

    @classmethod
    def list(cls):
        return [LambdaPriority(i) for i in range(LambdaPriority.num_priorities)]

    def __str__(self) -> str:
        return f"Lambda priority {self.value}" \
                if self.value >= 0 \
                else f"Lambda priority Undefined"
    
    def __repr__(self) -> str:
        return f"λᵖ({self.value if self.value >= 0 else 'N'})"

    def __hash__(self) -> int:
        return self.value.__hash__()
    
    def __eq__(self, other: object) -> bool:
        return isinstance(other,LambdaPriority) and self.value == other.value

def create_group(zapi, suffix):
    return zapi.hostgroup.create(
        name=f"group.{suffix}"
    )["groupids"][0]

def __is_ip(addr):
    try:
        for octet in addr.split('.'):
            o = int(octet)
            if not (o>=0 and o<256): return False
        return True
    except:
        return False

def interface_dict(addr,port):
    use_ip = __is_ip(addr)
    return {
        "ip": f"{addr if use_ip else ''}",
        "dns": f"{addr if not use_ip else ''}",
        "useip": f"{int(use_ip)}",
        "port": f"{port}"
    }

def create_host(zapi,suffix,group_ids: List[Union[str,int]], **kwargs):
    return zapi.host.create(
        host=suffix,
        groups=[{"groupid":f"{group_id}"} for group_id in group_ids],
        **kwargs
    )["hostids"][0]

def create_proxy(zapi,suffix,interface,active=False,**kwargs):
    status=["6","5"][int(active)]

    return zapi.proxy.create(
        host=f"proxy.{suffix}",
        status=status,
        interface=interface,
        **kwargs
    )["proxyids"][0]

class AllIn1MetricConfig:
    def __init__(self,
                 name:str,
                 type:str,
                 severity:ZabbixSeverity,
                 trigger_exp:str, 
                 aws_metric_name:str,
                 aws_statistic_name:str = "sum",
                 trigger_kwargs=None, 
                 item_kwargs=None):
        """
        :param trigger_exp: trigger expression for this metric,  with '{}' in place of the server, e.g. `'last({})>=3'` or `'count({},5m,"ge","5")>=1'`
        :param trigger_kwargs: other settings for the trigger. See Zabbix API for possible fields
        :param item_kwargs: other setting for the item. See Zabbix API for possible fields
        """
        self.name=name
        try:
           self.type = zabbix_type_dict[type]
        except: raise ValueError(f"Invalid metric type.")
        self.expr=trigger_exp
        self.severity=severity
        self.trigger_kwargs = trigger_kwargs or {}
        self.item_kwargs = item_kwargs or {}
        self.aws_metric=aws_metric_name
        self.aws_stat=aws_statistic_name

    def items(self,suffix,host_id):
        return {
            "name": f"{suffix} {self.name}",
            "key_": f"{self.name}.metrics.{suffix}",
            "hostid": f"{host_id}",
            "type": 2, # all trappers
            "value_type": self.type,
            **self.item_kwargs
        } 
    
    def triggers(self,suffix,zabbix_host=None,manual_close=True, **kwargs):
        zabbix_host = zabbix_host or suffix
        return {
            "description": f"{self.name}.triggers.{suffix}",
            "expression": self.expr.format(f"/{zabbix_host}/{self.items(suffix,0)['key_']}"),
            "manual_close": int(manual_close),
            "priority": self.severity.value
            **self.trigger_kwargs
        }

def error_count_string_metric():
    return AllIn1MetricConfig(
        name="error-count-string",
        type="text",
        trigger_exp= "countunique({},5m,\"regexp\",\"([A-Za-z0-9]+),\\1,\\1\")>0",
        trigger_kwargs={
            "type": 1,
            "correlation_mode": 1,
            "correlation_tag": "Lambda Name",
            "tags": [
                {
                    "tag": "Lambda Name",
                    "value":  "{{ITEM.VALUE}.regsub(\"([A-Za-z0-9]+),\\1,\\1\", \"\\1\")}"
                }
            ]
        }
    )

def create_all_in_one_item(
        zapi,
        suffix,
        metrics: List[AllIn1MetricConfig],
        group_id=None,
        host_id=None
        ):
    if not host_id:
        group_id = group_id or create_group(zapi,suffix)
    host_id = host_id or create_host(zapi,suffix)

    for metric in metrics:

        # create the metric item
        zapi.item.create(metric.items(suffix,host_id))

        # create trigger for the item
        zapi.trigger.create(metric.triggers(suffix))

class LLDSingleTriggerMetricConfig:
    def __init__(self, 
                 name:str, 
                 type:str, 
                 priority_map:Dict[LambdaPriority,Tuple[ZabbixSeverity,Union[int,float]]],
                 trigger_exp:str,
                 aws_metric_name:str,
                 aws_statistic_name:str = "sum",
                 trigger_kwargs:Dict[str,any]=None,
                 item_kwargs:Dict[str,any]=None):
        """
        :param: name:str = name for the metric,
        :param: trigger_exp:str = zabbix trigger expression where 
                            the server is replaced by {0} 
                            and relevant constant by {1} 
                            - they will be added in a create function 

                            - e.g. `'last({0})>{1}'`, `'count({0},5m,"ge","{1}")>=1'`,

        :param: type:str = value type of the metric: float, int, char, log or text,
        :param: const_mapping:[int] = list of constants to map lambda priorities to (lambda priorities are indexes, last value for unclassified lambdas), 
        :param: severity_mapping:[int] = list of zabbix severity codes (0-5) to map lambda priorities to (indexes as well), one less item than in const_mapping (severity for unlcasified is Not Classified...)

        :param: const_name:str = optional name for constants associated with this metric, default uppercase name
        """
        self.name=name
        try:
            self.type = zabbix_type_dict[type]
        except: raise ValueError(f"Invalid metric type: {type}")

        self.priority_map=priority_map
        self.expr=trigger_exp
        self.const = name.upper()
        self.trigger_kwargs=trigger_kwargs or {}
        self.item_kwargs=item_kwargs or {}
        self.aws_metric=aws_metric_name
        self.aws_stat=aws_statistic_name


    def _item_key(self,suffix,name_tag):
        return f"{self.name}.metrics.{suffix}[{{#{name_tag}}}]"

    def items(self,suffix,host_id,discovery_item_id,name_tag="FN_NAME"):
        return {
            "name": f"{{#{name_tag}}} {self.name}",
            "key_": self._item_key(suffix,name_tag),
            "value_type": self.type,
            "hostid": f"{host_id}",
            "ruleid": f"{discovery_item_id}",
            "type": 2, # trapper
            **self.item_kwargs
        }
    
    def _trigger_name(self,suffix,name_tag):
        return f"{self.name}.triggers.{suffix}[{{#{name_tag}}}]"
    
    def triggers(self,suffix,zabbix_host=None,name_tag="FN_NAME",prio_tag="PRIO",manual_close=True):
        zabbix_host = zabbix_host or suffix
        return {
            "description": self._trigger_name(suffix,name_tag),
            "manual_close": int(manual_close),
            "expression": self.expr.format(
                f"/{zabbix_host}/{self._item_key(suffix,name_tag)}",
                "{$%s:\\\"{#%s}\\\"}" % (self.const,prio_tag) # f-string: "{{${self.const}:\\\"{{#{prio_tag}}}\\\"}}"
            ),
            **self.trigger_kwargs
        }

    def macros(self,hostid):
        return [
            {
                "hostid": f"{hostid}",
                "macro": f'{{${self.const}:{i}}}', # who came up with this macro naming convention ffs??
                "value": f"{v}"
            }
            for i,v in map(lambda e: (e[0].value,e[1][1]), self.priority_map.items())
            if i != -1 # only macros with context here
        ] + [ 
            {
                "hostid": f"{hostid}",
                "macro": f'{{${self.const}}}',
                "value": f"{self.priority_map[LambdaPriority(-1)][1]}"
            } # default constant here
        ]
    
    def override_operations(self,suffix,priority,name_tag="FN_NAME"):
        return {
                "operationobject": "1", # trigger
                "operator": 2,
                "value": self._trigger_name(suffix,name_tag).split('[')[0],
                "opseverity": {"severity": self.priority_map[priority][0].value}
               }
    
def create_single_trigger_mapping(
        zapi: ZabbixAPI, 
        metrics: List[LLDSingleTriggerMetricConfig], 
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
    group_id = group_id or create_group(zapi, suffix)
    trapper_host_id = host_id or create_host(zapi,suffix,[group_id])

    # create LLD rule
    discovery_item_id=zapi.discoveryrule.create(
        name="Discover Lambda Functions",
        key_=f"discover.{suffix}",
        hostid=f"{trapper_host_id}",
        type=2 # trapper
    )["itemids"][0]
    
    # configure objects per-metric
    for metric in metrics:
        # create user macros with context -- maps lambda priorities to trigger constants (when the trigger triggers)
        #                                 -- for each metric and possible lambda priority
        zapi.usermacro.create(*metric.macros(trapper_host_id))
        
        # create item prototypes -- discovered items for each lambda, each lambda tracks each metric
        zapi.itemprototype.create(metric.items(suffix,trapper_host_id,discovery_item_id,name_tag))

        # create trigger prototypes -- for each discovered item (lambda), one trigger per metric
        #                           -- parametrized with constants (macros) and severities (overrides) for each lambda
        zapi.triggerprototype.create(metric.triggers(suffix,None,name_tag,prio_tag,True))

    # add overrides to LLD rules -- maps lambda priorities to zabbix severity (how severe a trigger is)
    #                            -- one for each priority, each updates severity for every metric trigger
    zapi.discoveryrule.update(
        itemid=f"{discovery_item_id}",
        overrides=[
            {
                "name": f"OV_PRIO_{i}",
                "step": f"{i+1}",
                "stop": 1, # stop if filter matches -- this override updates all triggers (of all metrics)
                "filter": {
                    "evaltype": "2",
                    "conditions": [
                        {
                            "macro": f"{{#{prio_tag}}}",
                            "operator": 8,
                            "value": f"^{i}$"
                        }
                    ]
                },
                "operations": [
                    metric.override_operations(suffix,priority,name_tag)
                    for metric in metrics
                ]
            }
        for i,priority in enumerate(LambdaPriority.list()) # iterate over all priorities
        ]
    )

    return trapper_host_id



class LLDMultiTriggerMetricConfig:
    def __init__(
            self,
            name:str,
            priority_mapping: Dict[LambdaPriority,Dict[ZabbixSeverity,Union[int,float,None]]],
            zbx_trigger_expression_pattern: str,
            zbx_value_type:str,
            aws_metric_name:str,
            aws_statistic_name:str,
            trigger_kwargs:Dict[str,any]=None,
            item_kwargs:Dict[str,any]=None
    ):
        """
        :param name: name of the metric
        :param priority_mapping: nested dictionary that maps Lambda priorities to constants for each Zabbix severity, some items can be omitted
        :param trigger_expression_pattern: pattern for all the expressions (same), with "server" field and a compare-to value substituted with {},
                                           e.g. `last({})>{}` or `count({},5m,"ge","{}")>=1` -- will be fed accordingly
        :param value_type: Zabbix value type (int,float,char,text,log)
        :param zbx_item: name of the item prototype in Zabbix. If None, name of the metric is used
        """
        self.name=name
        self.aws_metric = aws_metric_name
        self.aws_stat = aws_statistic_name
        self.const = name.upper()
        self.priority_map=priority_mapping
        self.expr = zbx_trigger_expression_pattern
        self.type = zabbix_type_dict[zbx_value_type]
        self.item_name = f"{aws_statistic_name.lower()}.{aws_metric_name.lower()}"
        self.trigger_kwargs=trigger_kwargs or {}
        self.item_kwargs=item_kwargs or {}

        def keep_trigger(priority, severity):
            return priority in self.priority_map and \
               severity in self.priority_map[priority] # and \
               #self.priority_map[priority][severity] is not None 
               # -- this check is not needed to compute, but a "None" value also means "don't keep"
        
        self.priority_map={
            priority: {
                severity: priority_mapping[priority][severity] if keep_trigger(priority,severity) else None
                for severity in list(ZabbixSeverity)
                }
            for priority in LambdaPriority.list() + [LambdaPriority(-1)]
            }

    def items(self,suffix,host_id,discovery_item_id,name_tag="FN_NAME"):
        return {
            "name": f"{{#{name_tag}}} {self.item_name}",
            "key_": f"{self.item_name}.metrics.{suffix}[{{#{name_tag}}}]",
            "value_type": self.type,
            "hostid": f"{host_id}",
            "ruleid":f"{discovery_item_id}",
            "type": 2, # trapper
            **self.item_kwargs
        }
    
    def triggers(self,severity:ZabbixSeverity,suffix:str,depends_on_ids=None,zabbix_host=None,name_tag="FN_NAME",prio_tag="PRIO",manual_close=True):
        zabbix_host = zabbix_host or suffix
        dependencies = {"dependencies": [{"triggerid":f"{id}"} for id in depends_on_ids]} if depends_on_ids else {}
        return {
            "description": f"{severity.name}.{self.name}.triggers.{suffix}[{{#{name_tag}}}]",
            "manual_close": int(manual_close),
            "priority": severity.value,
            "expression": self.expr.format(
                f"/{zabbix_host}/{self.items(suffix,0,0,name_tag)['key_']}",
                "{$%s_%s:\\\"{#%s}\\\"}" % (self.const, severity.name, f"{self.name.upper()}_{prio_tag}") # f-string: "{{${self.const}_{severity.name}:\\\"{{#{self.name.upper()}_{prio_tag}}}\\\"}}"
            ),
            **dependencies,
            **self.trigger_kwargs
        } if any(prio[severity] for prio in self.priority_map.values()) else {}

    def macros(self,severity:ZabbixSeverity,hostid):
        return [
            {
                "hostid": f"{hostid}",
                "macro": f'{{${self.const}_{severity.name}:"{priority.value}"}}', 
                "value": f"{self.priority_map[priority][severity]}"
            }
            for priority in [LambdaPriority(i) for i in range(LambdaPriority.num_priorities)]
            if self.priority_map[priority][severity] is not None # only context macros that are defined and specified
        ] + [
            {
                "hostid": f"{hostid}",
                "macro": f'{{${self.const}_{severity.name}}}', 
                "value": f"{self.priority_map[LambdaPriority(-1)][severity] or 1<<24}"
            } # default macro (for undefined priority)
        ]
    
    def override_operations(self,suffix,priority,name_tag="FN_NAME"):
        return [
            {
                "operationobject": "1", # trigger prototype
                "operator": 2,
                "value": trigger["description"].split('[')[0],
                "opstatus": {"status":1}, # don't create
                "opdiscover":{"discover":1} # don't discover
            }
            for severity in list(ZabbixSeverity)
            for trigger in [self.triggers(severity,suffix,name_tag=name_tag)]
            if trigger
            if self.priority_map[priority][severity] is None
        ]
    
    def overrides(self,suffix,step_counter,name_tag="FN_NAME",prio_tag="PRIO"):
        macro_name = f"{self.name.upper()}_{prio_tag}"
        return [
            # if priority macro does not exist, do not create triggers
            {
                "name": f"OV_{macro_name}_N",
                "step": f"{next(step_counter)}",
                "stop": 0,
                "filter": {
                    "evaltype": "2", # OR
                    "conditions": [
                        {
                            "macro": f"{{#{macro_name}}}",
                            "operator": 13, # does not exist
                            "value": "" 
                        }
                    ]
                },
                "operations": [
                    # do not create triggers
                    {
                        "operationobject": "1", # trigger prototype
                        "operator": 2,
                        "value": f"{self.name}.triggers.{suffix}",
                        "opstatus": {"status":1}, # don't create
                        "opdiscover":{"discover":1} # don't discover
                    }
                ]
            }
            for _ in [...] # to have an if clause, lol
            if any(self.priority_map[p][s] for p in LambdaPriority.list() for s in list(ZabbixSeverity)) # do not create if priority map is empty
        ] +  [ 
            # overrides based on priority -- do not discover unused severities for the priority
            {
                "name": f"OV_{macro_name}_{priority.value}",
                "step": f"{next(step_counter)}",
                "stop": 0,
                "filter": {
                    "evaltype": "1", # AND
                    "conditions": [
                        {
                            "macro": f"{{#{macro_name}}}",
                            "operator": 12, # exists
                            "value": "" 
                        },
                        {
                            "macro": f"{{#{macro_name}}}",
                            "operator": 8,  # matches
                            "value": f"^{priority.value}$"
                        }
                    ]
                },
                "operations": operations
            }
        for priority in LambdaPriority.list()
        for operations in [self.override_operations(suffix,priority,name_tag)]
        if operations # do not create rule with no operations
        ] + [ 
            # override for unclassified lambda (=undefined priority)
            {
                "name": f"OV_{macro_name}_U",
                "step": f"{next(step_counter)}",
                "stop": 0, 
                "filter": {
                    "evaltype": "1", # AND
                    "conditions": [
                        {   
                            "macro": f"{{#{macro_name}}}",
                            "operator": 12, # exists
                            "value": ""
                        },
                        {   
                            "macro": f"{{#{macro_name}}}",
                            "operator": 9,  # does not match
                            "value": f"^[0-{LambdaPriority.num_priorities-1}]$"
                        }
                    ]
                },
                "operations": operations
            }
            for operations in [self.override_operations(suffix,LambdaPriority(-1),name_tag)]
            if operations # same reason as above
        ]
    
def create_multi_trigger_mapping(
        zapi: ZabbixAPI, 
        metrics: List[LLDMultiTriggerMetricConfig], 
        suffix="lambda.zblamb", 
        prio_tag="PRIO", 
        name_tag="FN_NAME",
        group_id=None,
        host_id=None):
    """
    :param: zapi ZabbixAPI instance
    :param: suffix Suffix to use for lambda discovery objects
    :param: metrics list of MetricConfig
    :param lifetime: Time period after which items that are no longer discovered will be deleted. Accepts time unit with suffix
    :param: group_id Zabbix ID of the group to add the host to
    :param: host_id Zabbix ID of the host to add discovery to.
    """
    # create host
    try:
        group_id = group_id or create_group(zapi, suffix)
    except ZabbixAPIException as e:
        if "already exists" in e.error["data"]:
            group_id = zapi.hostgroup.get(
                search= { "name": f"group.{suffix}" },
                output=['groupid']
            )[0]['groupid']
        else: raise e

    try:
        trapper_host_id = host_id or create_host(zapi,suffix,[group_id])
    except ZabbixAPIException as e:
        if "already exists" in e.error["data"]:
            trapper_host_id = zapi.host.get(
                search= { "host": f"{suffix}" },
                output=['hostid']
            )[0]['hostid']
        else: raise e

    # create LLD rule
    try:
        discovery_item_id=zapi.discoveryrule.create(
            name="Discover Lambda Functions with Multi-level Triggers",
            key_=f"discover.{suffix}",
            hostid=f"{trapper_host_id}",
            lifetime=ZBX_LLD_KEEP_PERIOD,
            type=2 # trapper
        )["itemids"][0]
    except ZabbixAPIException as e:
        if "already exists" in e.error["data"]:
            discovery_item_id = zapi.discoveryrule.get(
                search= { "key_": f"discover.{suffix}" },
                output=['itemid']
            )[0]['itemid']
        else: raise e

    for metric in metrics:
        zapi.usermacro.create(
        *list(itertools.chain.from_iterable(
            [metric.macros(severity,trapper_host_id) for severity in list(ZabbixSeverity)]
        )))

        try:
            zapi.itemprototype.create(metric.items(suffix,trapper_host_id,discovery_item_id,name_tag))
        except ZabbixAPIException as e:
            if "already exists" in e.error["data"]:      # add triggers to an already existing prototype
                pass
            else: raise e

        depends_on_ids=[]
        for severity in reversed(list(ZabbixSeverity)): # highest severity first
            trigger = metric.triggers(severity,suffix,depends_on_ids,None,name_tag,prio_tag)
            if trigger:
                depends_on_ids.append(
                    zapi.triggerprototype.create( trigger )["triggerids"][0]
                )

    # add overrides to LLD rules 
    counter = itertools.count(1)
    zapi.discoveryrule.update(
        itemid=f"{discovery_item_id}",
        overrides= list(itertools.chain.from_iterable([
            metric.overrides(suffix,counter,name_tag,prio_tag)
            for metric in metrics
        ]))
    )