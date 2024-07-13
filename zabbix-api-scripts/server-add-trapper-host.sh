#!/bin/bash

: "${ZBLAMB_TOKEN:?'Authorize first using get-cred.sh!'}"
#: "${ZBLAMB_PROXY_ID:?'Create a proxy first using server-add-proxy.sh!'}"
: "${ZBLAMB_GROUP_ID:?'Create a host group first using server-add-host-group.sh!'}"
: "${ZBLAMB_FRONTEND_HNAME:=localhost}"

trapper_keys=("error-stream" "error-log" "error-counts" "error-count-string")
trapper_types=(1 2 3 4)

# create trapper host

DATA=$(cat data/server-add-trapper-host.json | \
       sed -e "s/ZBLAMB_GROUP_ID/$ZBLAMB_GROUP_ID/g"  \
           -e "s/ZBLAMB_TOKEN/$ZBLAMB_TOKEN/g" | \
        jq -c) 

TRAPPER_HOST_ID=\
$(curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data $DATA | \
jq -r ".result.hostids[0]")

# add trapper items

for i in "${!trapper_keys[@]}"; do 

DATA=$(cat data/host-add-trapper-item.json | \
        sed -e "s/TRAPPER_KEY/${trapper_keys[$i]}/g" \
            -e "s/\"TRAPPER_VALUE_TYPE\"/${trapper_types[$i]}/g" \
            -e "s/ZBLAMB_TRAPPER_HOST_ID/$TRAPPER_HOST_ID/" \
            -e "s/ZBLAMB_TOKEN/$ZBLAMB_TOKEN/" | \
        jq -c)


curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data $DATA 

done

echo $TRAPPER_HOST_ID
