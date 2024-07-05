#!/bin/bash

: "${ZBLAMB_FRONTEND_HNAME:=localhost}"
export ZBLAMB_FRONTEND_HNAME=$ZBLAMB_FRONTEND_HNAME
: "${ZBLAMB_PROXY_HNAME:=localhost}"
export ZBLAMB_PROXY_HNAME=$ZBLAMB_PROXY_HNAME

export ZBLAMB_TOKEN=$(./get-cred.sh)
export $ZBLAMB_PROXY_ID=$(./server-add-proxy.sh)
export $ZBLAMB_GROUP_ID=$(./server-add-host-group.sh)
./server-add-host.sh
./logout.sh

