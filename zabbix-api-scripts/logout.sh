#!/bin/bash
: "${ZBLAMB_TOKEN:?'Authorize first using get-cred.sh!'}"
: "${ZBLAMB_FRONTEND_HNAME:=localhost}"

curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --header "Authorization: Bearer $ZBLAMB_TOKEN" \
  --data '{"jsonrpc":"2.0","method":"user.logout","params":[],"id":1,"auth": "'$ZBLAMB_TOKEN'"}' | \
jq #".result"
