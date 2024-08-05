from .zapi import LLDMultiTriggerMetricConfig 
from .zapi import LambdaPriority, ZabbixSeverity

MetricConfigs = [
        LLDMultiTriggerMetricConfig(
            zbx_name="errors",
            zbx_value_type="int",
            zbx_trigger_expression_pattern='count({},5m,"ge","{}")>="1"',
            aws_metric_name='Errors',
            aws_statistic_name='sum',
            priority_mapping={
                LambdaPriority(0): { ZabbixSeverity.DISASTER: 1 },                                                      # prio 0 triggers disaster on at least one fail
                LambdaPriority(1): { ZabbixSeverity.DISASTER: 2,   ZabbixSeverity.HIGH: 1},                             # prio 1 triggers disaster on at least 2 fails and high on 1 fail
                LambdaPriority(2): { ZabbixSeverity.DISASTER: None,ZabbixSeverity.HIGH: 2, ZabbixSeverity.AVERAGE: 1},  # prio 2 triggers high on at least 2 fails and average on 1 fail
                LambdaPriority(-1): {severity: None for severity in list(ZabbixSeverity)}                               # undefined priority does not trigger anything
            }
        ),
        LLDMultiTriggerMetricConfig(
            zbx_name="max.duration",
            zbx_value_type="float",
            zbx_trigger_expression_pattern='last({})>="{}"',
            aws_metric_name='Duration',
            aws_statistic_name='max',
            priority_mapping={
                LambdaPriority(0): { ZabbixSeverity.DISASTER: 1000.0 },                                 # prio 0 triggers disaster if a function took longer than 1 s
                LambdaPriority(1): { ZabbixSeverity.DISASTER: 1500.0,   ZabbixSeverity.HIGH: 750.0},    
                LambdaPriority(2): { ZabbixSeverity.HIGH: 1000.0, ZabbixSeverity.AVERAGE: 500.},        
            }
        ),
        LLDMultiTriggerMetricConfig(
            zbx_name="min.duration",
            zbx_value_type="float",
            zbx_trigger_expression_pattern='last({})>="{}"',
            aws_metric_name='Duration',
            aws_statistic_name='min',
            priority_mapping={
                LambdaPriority(0): { ZabbixSeverity.DISASTER: 100.0 },                              # prio 0 triggers disaster if all functions took longer than 100 ms
                LambdaPriority(1): { ZabbixSeverity.DISASTER: 150.0,   ZabbixSeverity.HIGH: 75.0},  
                LambdaPriority(2): { ZabbixSeverity.HIGH: 100.0, ZabbixSeverity.AVERAGE: 50.},      
            }
        ),
        LLDMultiTriggerMetricConfig(
            zbx_name="count_avg.duration",
            zbx_value_type="float",
            # more than 4 invocations took longer than <const> ms or 
            # the average of slowest (= max duariton) invocations is greater than <const> ms 
            # for the past 5 minutes
            zbx_trigger_expression_pattern='count({0},5m,"ge","{1}")>4 or avg({0},5m)>"{1}"', 
            aws_metric_name="Duration",
            aws_statistic_name="max",

            priority_mapping={
                LambdaPriority(1): { ZabbixSeverity.HIGH: 500, ZabbixSeverity.AVERAGE: 400},    
                LambdaPriority(2): { ZabbixSeverity.AVERAGE: 400},        
            }
        )
]