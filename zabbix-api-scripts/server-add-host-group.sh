#!/bin/bash

: "${ZBLAMB_TOKEN:?'Authorize first using get-cred.sh!'}"
: "${ZBLAMB_FRONTEND_HNAME:=localhost}"


curl -s --request POST \
  --url "https://$ZBLAMB_FRONTEND_HNAME/zabbix/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data $(cat data/server-add-host-group.json) | \
jq ".result.groupids[0]"