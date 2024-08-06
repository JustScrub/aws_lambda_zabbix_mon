ZBX_SUFFIX="multi.lambda.zblamb" # Zabbix objects base/root name
AWS_PRIO_TAG="PRIO" # Name of Lambda Functions Tag that yields the function's priority
ZBX_PRIO_MACRO="PRIO" # Zabbix LLD Macro that yields the discovered function priority
ZBX_FN_NAME_MACRO="FN_NAME" # Zabbix LLD Macro that yields the discovered function name
ZBX_MONITORED_TAG="ZabbixMonitorExpireTime" # Name of Lambda Function Tag that stores nanosecond timestamp after which Zabbix will un-discover the function
ZBX_LLD_KEEP_PERIOD="2592000" # How long Zabbix keeps discovered entities in seconds if no new data have been recieved
AWS_TRANSFORM_TIMEOUT="3" # Timeout of the Transformation Lambda
