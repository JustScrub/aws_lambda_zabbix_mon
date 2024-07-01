#!/bin/bash

: "${ZBLAMB_TOKEN:?'Authorize first using get-cred.sh!'}"
: "${ZBLAMB_FRONTEND_HNAME:=localhost}"
: "${ZBLAMB_PROXY_HNAME:=localhost}"

curl -s --request POST \
  --url "https://$ZBLAMB_FRONTEND_HNAME/zabbix/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data $(sed "s/ZBLAMB_PROXY_HNAME/$ZBLAMB_PROXY_HNAME/g" < data/server-add-proxy.json) | \
jq ".result.proxyids[0]"