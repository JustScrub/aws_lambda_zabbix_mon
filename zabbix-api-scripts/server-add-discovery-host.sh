#!/bin/bash

: "${ZBLAMB_TOKEN:?'Authorize first using get-cred.sh!'}"
#: "${ZBLAMB_PROXY_ID:?'Create a proxy first using server-add-proxy.sh!'}"
: "${ZBLAMB_GROUP_ID:?'Create a host group first using server-add-host-group.sh!'}"
: "${ZBLAMB_FRONTEND_HNAME:=localhost}"

: "${ZBLAMB_DISCOVERY_SUFFIX:='lambda.zblamb'}"
: "${ZBLAMB_LAMBDA_PRIORITY_TAG:='PRIO'}"
: "${ZBLAMB_LAMBDA_NAME_TAG:='FN_NAME'}"

# CONFIGURATION
severity_mapping=(5 5 4 4 4 3 3 2 2 1 0)
const_mapping=(1 2 1 1 2 2 3 3 3 4 1)

# create trapper host

DATA=$(cat data/server-add-trapper-host.json | \
       sed -e "s/ZBLAMB_GROUP_ID/$ZBLAMB_GROUP_ID/g"  \
           -e "s/HOST_NAME/$ZBLAMB_DISCOVERY_SUFFIX/"  \
           -e "s/ZBLAMB_TOKEN/$ZBLAMB_TOKEN/g" | \
        jq -c) 

TRAPPER_HOST_ID=\
$(curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data $DATA | \
jq -r ".result.hostids[0]")

# make to loops
metric="errors"
metric_const="ZBLAMB_ERROR_CONST" #  will loop through these when there are more metrics
metric_expression="count(\\/$ZBLAMB_DISCOVERY_SUFFIX\\/$metric.metrics.$ZBLAMB_DISCOVERY_SUFFIX[{#$ZBLAMB_LAMBDA_NAME_TAG}],5m,\"ge\",\"{\$$metric_const:{#$ZBLAMB_LAMBDA_PRIORITY_TAG}}\")>=1"

# create constant macros

for i in "${!const_mapping[@]}"; do 

DATA=$(cat data/server-add-usermacro.json | \
       sed -e "s/HOST_ID/$TRAPPER_HOST_ID/" \
           -e "s/VALUE/${const_mapping[$i]}/" \
           -e "s/MACRO/$metric_const:$i/" \
           -e "s/ZBLAMB_TOKEN/$ZBLAMB_TOKEN/" |\
       jq -c)


curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data $DATA > /dev/null

done

# create LLD

DATA=$(cat data/trapper-host-lambda-discovery.json | \
       sed -e "s/TRAPPER_HOST_ID/$TRAPPER_HOST_ID/" \
           -e "s/ZBLAMB_TOKEN/$ZBLAMB_TOKEN/" \
           -e "s/LLD_KEY/discover.$ZBLAMB_DISCOVERY_SUFFIX/") | \
       jq -c


DISCOVERY_ITEM_ID=\
$(curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data @- <<< $DATA | \
jq -r ".result.itemids[0]")

# add overrides to the LLD

# loop metrics as well
for i in "${!severity_mapping[@]}"; do 

DATA=$(cat data/lld-add-trigger-severity-override.json | \
       sed -e "s/TRAPPER_HOST_ID/$TRAPPER_HOST_ID/" \
           -e "s/OVERRIDE_NAME/OV_$metric:$i/" \
           -e "s/STEP/$i/" \
           -e "s/MACRO/$ZBLAMB_LAMBDA_PRIORITY_TAG/" \
           -e "s/PRIORITY_VALUE/$i/" \
           -e "s/OVERRIDE_TRIGGER_NAME/$metric.triggers.$ZBLAMB_DISCOVERY_SUFFIX/" \
           -e "s/OVERRIDE_SEVERITY/${severity_mapping[$i]}/" \
           -e "s/ZBLAMB_TOKEN/$ZBLAMB_TOKEN/" | \
        jq -c)

$(curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data @- <<< $DATA > /dev/null)


done

# create item prototypes

# loop metrics
DATA=$(cat data/lld-add-float-trapper-item-proto.json | \
       sed -e "s/TRAPPER_HOST_ID/$TRAPPER_HOST_ID/" \
           -e "s/ITEM_KEY/$metric.metrics.$ZBLAMB_DISCOVERY_SUFFIX[{#$ZBLAMB_LAMBDA_NAME_TAG}]/" \
           -e "s/ITEM_NAME/$ZBLAMB_LAMBDA_NAME_TAG $metric item/" \
           -e "s/DISCOVERY_ITEM_ID/$DISCOVERY_ITEM_ID/" \
           -e "s/ZBLAMB_TOKEN/$ZBLAMB_TOKEN/" | \
        jq -c)

$(curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data @- <<< $DATA > /dev/null)


# create trigger prototypes

# loop metrics
DATA=$(cat data/lld-add-trigger-proto.json | \
       sed -e "s/TRIGGER_NAME/$ZBLAMB_LAMBDA_NAME_TAG $metric trigger/" \
           -e "s/TRIGGER_EXP/$metric_expression/" \
           -e "s/ZBLAMB_TOKEN/$ZBLAMB_TOKEN/" | \
        jq -c)

$(curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data @- <<< $DATA > /dev/null)

echo $TRAPPER_HOST_ID