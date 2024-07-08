#!/bin/bash

: "${ZBLAMB_TOKEN:?'Authorize first using get-cred.sh!'}"
: "${ZBLAMB_PROXY_ID:?'Create a proxy first using server-add-proxy.sh!'}"
: "${ZBLAMB_GROUP_ID:?'Create a host group first using server-add-host-group.sh!'}"
: "${ZBLAMB_AGENT_IP:?'To create a host, you must provide server-reachable IP of this machine!'}"
: "${ZBLAMB_FRONTEND_HNAME:=localhost}"

DATA=$(cat data/server-add-host.json | \
       sed -e "s/ZBLAMB_PROXY_ID/$ZBLAMB_PROXY_ID/g" \
           -e "s/ZBLAMB_GROUP_ID/$ZBLAMB_GROUP_ID/g"  \
           -e "s/ZBLAMB_TOKEN/$ZBLAMB_TOKEN/g"  \
           -e "s/ZBLAMB_AGENT_IP/$ZBLAMB_AGENT_IP/g" | \
        jq -c) 

curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data $DATA | \
jq -r ".result.hostids[0]"