from scripts.zapi import LLDMultiTriggerMetricConfig 
from scripts.zapi import LambdaPriority, ZabbixSeverity

MetricConfigs = [
        # Errors metric
        LLDMultiTriggerMetricConfig(
            name="errors",
            zbx_value_type="int",
            zbx_trigger_expression_pattern='count({},5m,"ge","{}")>="1"',
            aws_metric_name='Errors',
            aws_statistic_name='sum',
            priority_mapping={
                LambdaPriority(0): { ZabbixSeverity.DISASTER: 1 },                                                      # prio 0 triggers disaster on at least one fail
                LambdaPriority(1): { ZabbixSeverity.DISASTER: 2,   ZabbixSeverity.HIGH: 1},                             # prio 1 triggers disaster on at least 2 fails and high on 1 fail
                LambdaPriority(2): { ZabbixSeverity.DISASTER: None,ZabbixSeverity.HIGH: 2, ZabbixSeverity.AVERAGE: 1},  # prio 2 triggers high on at least 2 fails and average on 1 fail
                LambdaPriority(3): { ZabbixSeverity.HIGH: 3, ZabbixSeverity.AVERAGE: 2, ZabbixSeverity.WARNING: 1},
                LambdaPriority(-1): {severity: None for severity in list(ZabbixSeverity)}   # undefined priority does not trigger anything
            }
        ),
        # Metrics based on expected duration: fast function, medium functions and slow functions
        # Priority here states the "severity level" -- all constants are same, just severities are lowered
        LLDMultiTriggerMetricConfig(
            name="500ms.duration",    # fast functions below 500 ms
            zbx_value_type="float",
            zbx_trigger_expression_pattern='last({})>="{}"',
            aws_metric_name='Duration',
            aws_statistic_name='max',
            priority_mapping={
                LambdaPriority(0): { ZabbixSeverity.DISASTER:  1000.0,   ZabbixSeverity.HIGH:         750.0, ZabbixSeverity.AVERAGE:     500.1 },
                LambdaPriority(1): { ZabbixSeverity.HIGH:      1000.0,   ZabbixSeverity.AVERAGE:      750.0, ZabbixSeverity.WARNING:     500.1 },
                LambdaPriority(2): { ZabbixSeverity.HIGH:      1000.0,   ZabbixSeverity.AVERAGE:      750.0},
                LambdaPriority(3): { ZabbixSeverity.AVERAGE:   1000.0,   ZabbixSeverity.WARNING:      750.0},
                LambdaPriority(4): { ZabbixSeverity.WARNING:   1000.0,   ZabbixSeverity.INFORMATION:  750.0},
                LambdaPriority(-1):{ ZabbixSeverity.NOT_CLASSIFIED: 1000.0}
            }
        ),
        LLDMultiTriggerMetricConfig(
            name="2000ms.duration",    # medium fast functions below 2 s
            zbx_value_type="float",
            zbx_trigger_expression_pattern='last({})>="{}"',
            aws_metric_name='Duration',
            aws_statistic_name='max',
            priority_mapping={
                LambdaPriority(0): { ZabbixSeverity.DISASTER:  5000.0,   ZabbixSeverity.HIGH:         3000.0, ZabbixSeverity.AVERAGE:     2000.0 },
                LambdaPriority(1): { ZabbixSeverity.HIGH:      5000.0,   ZabbixSeverity.AVERAGE:      3000.0, ZabbixSeverity.WARNING:     2000.0 },
                LambdaPriority(2): { ZabbixSeverity.HIGH:      5000.0,   ZabbixSeverity.AVERAGE:      3000.0},
                LambdaPriority(3): { ZabbixSeverity.AVERAGE:   5000.0,   ZabbixSeverity.WARNING:      3000.0},
                LambdaPriority(4): { ZabbixSeverity.WARNING:   5000.0,   ZabbixSeverity.INFORMATION:  3000.0},
                LambdaPriority(-1):{ ZabbixSeverity.NOT_CLASSIFIED: 5000.0}
            }
        ),
        LLDMultiTriggerMetricConfig(
            name="5000ms.duration",    # slow functions below 5 s
            zbx_value_type="float",
            zbx_trigger_expression_pattern='last({})>="{}"',
            aws_metric_name='Duration',
            aws_statistic_name='max',
            priority_mapping={
                LambdaPriority(0): { ZabbixSeverity.DISASTER:  10000.0,   ZabbixSeverity.HIGH:         7000.0, ZabbixSeverity.AVERAGE:     5000.0 },
                LambdaPriority(1): { ZabbixSeverity.HIGH:      10000.0,   ZabbixSeverity.AVERAGE:      7000.0, ZabbixSeverity.WARNING:     5000.0 },
                LambdaPriority(2): { ZabbixSeverity.HIGH:      10000.0,   ZabbixSeverity.AVERAGE:      7000.0},
                LambdaPriority(3): { ZabbixSeverity.AVERAGE:   10000.0,   ZabbixSeverity.WARNING:      7000.0},
                LambdaPriority(4): { ZabbixSeverity.WARNING:   10000.0,   ZabbixSeverity.INFORMATION:  7000.0},
                LambdaPriority(-1):{ ZabbixSeverity.NOT_CLASSIFIED: 10000.0}
            }
        ),
        # Complex expression example
        LLDMultiTriggerMetricConfig(
            name="count_avg.duration",
            zbx_value_type="float",
            # more than 4 invocation batches took longer than <const> ms or 
            # the average of fastest (= min duariton) invocations is greater than <const> ms 
            # for the past 5 minutes
            zbx_trigger_expression_pattern='count({0},5m,"ge","{1}")>4 or avg({0},5m)>"{1}"', 
            aws_metric_name="Duration",
            aws_statistic_name="min",
            
            priority_mapping={
                LambdaPriority(1): { ZabbixSeverity.HIGH: 2000.0, ZabbixSeverity.AVERAGE: 1000.0},    
                LambdaPriority(2): { ZabbixSeverity.AVERAGE: 1500.0},        
            }
        ),
        # No priority mapping example
        LLDMultiTriggerMetricConfig(
            name="invocs",
            zbx_value_type="int",
            zbx_trigger_expression_pattern='last({0})>="{1}"',
            aws_metric_name="Invocations",
            aws_statistic_name="sum",
            priority_mapping={} # no triggers actually created, but expression still required
        )
]