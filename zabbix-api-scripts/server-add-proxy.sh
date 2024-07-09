#!/bin/bash

: "${ZBLAMB_TOKEN:?'Authorize first using get-cred.sh!'}"
: "${ZBLAMB_PROXY_IP:?'Specify reachable Proxy IP!'}"
: "${ZBLAMB_FRONTEND_HNAME:=localhost}"

DATA=$(cat data/server-add-proxy.json | \
       sed -e "s/ZBLAMB_PROXY_IP/$ZBLAMB_PROXY_IP/g" \
           -e "s/ZBLAMB_TOKEN/$ZBLAMB_TOKEN/g" | \
        jq -c)

curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data  $DATA | \
jq -r ".result.proxyids[0]"