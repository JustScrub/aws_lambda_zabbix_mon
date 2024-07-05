#!/bin/bash

: "${ZBLAMB_TOKEN:?'Authorize first using get-cred.sh!'}"
: "${ZBLAMB_FRONTEND_HNAME:=localhost}"
: "${ZBLAMB_PROXY_HNAME:=localhost}"

DATA=$(cat data/server-add-proxy.json | \
       sed -e "s/ZBLAMB_PROXY_HNAME/$ZBLAMB_PROXY_HNAME/g" \
           -e "s/ZBLAMB_TOKEN/$ZBLAMB_TOKEN" | \
        jq -c)

curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data  $DATA | \
jq ".result.proxyids[0]"