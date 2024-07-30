from scripts.zapi import LLDMultiTriggerMetricConfig #, AllIn1MetricConfig, LLDSingleTriggerMetricConfig
from scripts.zapi import LambdaPriority, ZabbixSeverity

MetricConfigs = [
        LLDMultiTriggerMetricConfig(
            zbx_name="errors",
            zbx_value_type="int",
            zbx_trigger_expression_pattern='count({},5m,"ge","{}")>=1',
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
            zbx_trigger_expression_pattern='last({})>={}',
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
            zbx_trigger_expression_pattern='last({})>={}',
            aws_metric_name='Duration',
            aws_statistic_name='min',
            priority_mapping={
                LambdaPriority(0): { ZabbixSeverity.DISASTER: 100.0 },                              # prio 0 triggers disaster if all functions took longer than 100 ms
                LambdaPriority(1): { ZabbixSeverity.DISASTER: 150.0,   ZabbixSeverity.HIGH: 75.0},  
                LambdaPriority(2): { ZabbixSeverity.HIGH: 100.0, ZabbixSeverity.AVERAGE: 50.},      
            }
        ),
        LLDMultiTriggerMetricConfig(
            zbx_name="countmin.duration",
            zbx_value_type="float",
            zbx_trigger_expression_pattern="count({},5m,ge,500)>{}", # when the number of functions that took longer than 300 ms is more than <const>
            aws_metric_name="Duration",
            aws_statistic_name="min",

            priority_mapping={
                LambdaPriority(1): { ZabbixSeverity.DISASTER: 2,   ZabbixSeverity.HIGH: 1},    
                LambdaPriority(2): { ZabbixSeverity.AVERAGE: 1},        
            }
        )
]