ZBX_SUFFIX="lambdas" # Zabbix objects base/root name
AWS_PRIO_TAG="PRIO" # Name of Lambda Functions Tag that yields the function's priority
ZBX_LLD_KEEP_PERIOD="0" # How long Zabbix keeps discovered entities in seconds if no new data have been recieved
ZBX_PRIO_MACRO="PRIO" # Zabbix LLD Macro that yields the discovered function priority
ZBX_FN_NAME_MACRO="FN_NAME" # Zabbix LLD Macro that yields the discovered function name
N_LAMBDA_PRIORITIES="5" # Number of Lambda priorities
AWS_DISCOVERED_TAG="ZBXdiscovered" # Name of Lambda Tag that specifies the function is discovered in Zabbix
