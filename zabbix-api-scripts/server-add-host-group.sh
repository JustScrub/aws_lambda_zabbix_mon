#!/bin/bash

: "${ZBLAMB_TOKEN:?'Authorize first using get-cred.sh!'}"
: "${ZBLAMB_FRONTEND_HNAME:=localhost}"

DATA=$(cat data/server-add-host-group.json | jq -c | sed "s/ZBLAMB_TOKEN/$ZBLAMB_TOKEN/g")

curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data $DATA | \
jq -r ".result.groupids[0]"