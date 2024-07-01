#!/bin/bash

: "${ZBLAMB_TOKEN:?'Authorize first using get-cred.sh!'}"
: "${ZBLAMB_PROXY_ID:?'Create a proxy first using server-add-proxy.sh!'}"
: "${ZBLAMB_GROUP_ID:?'Create a host group first using server-add-host-group.sh!'}"
: "${ZBLAMB_FRONTEND_HNAME:=localhost}"

curl -s --request POST \
  --url "https://$ZBLAMB_FRONTEND_HNAME/zabbix/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data $(cat data/server-add-host.json | \
           sed "s/ZBLAMB_PROXY_ID/$ZBLAMB_PROXY_ID/g" | \
           sed "s/ZBLAMB_GROUP_ID/$ZBLAMB_GROUP_ID/g") | \
jq ".result.hostids[0]"