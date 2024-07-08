#!/bin/bash
: "${ZBLAMB_FRONTEND_HNAME:=localhost}"
: "${ZBLAMB_ZB_USER:=Admin}"
: "${ZBLAMB_ZB_PWD:=zabbix}"

curl -s --request POST \
  --url "http://$ZBLAMB_FRONTEND_HNAME/api_jsonrpc.php" \
  --header 'Content-Type: application/json-rpc' \
  --data '{"jsonrpc":"2.0","method":"user.login","params":{"username":"'$ZBLAMB_ZB_USER'","password":"'$ZBLAMB_ZB_PWD'"},"id":1}' | \
jq -r ".result"

# -r to omit quotes
