#!/bin/bash

export ZBLAMB_FRONTEND_HNAME=${ZBLAMB_FRONTEND_HNAME:?'Frontend IP or DNS name must be specified'}

if [ -z $ZBLAMB_PROXY_ID ]; then
    export ZBLAMB_PROXY_IP=${ZBLAMB_PROXY_IP:?'Server-reachable Proxy IP must be specified'}
fi

# LOCAL IP for host creation -- Zabbix v5.4 needs it in API call
if [ -z $ZBLAMB_AGENT_IP ]; then
    IMDS_TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 10")
    export ZBLAMB_AGENT_IP=$(curl -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" http://169.254.169.254/latest/meta-data/local-ipv4)
fi

to_logout=0
if [ -z $ZBLAMB_TOKEN ]; then
    export ZBLAMB_TOKEN=$(./get-cred.sh)
    to_logout=1
fi

if [ -z $ZBLAMB_PROXY_ID ]; then
    export ZBLAMB_PROXY_ID=$(./server-add-proxy.sh)
fi

if [-z $ZBLAMB_GROUP_ID]; then
    export ZBLAMB_GROUP_ID=$(./server-add-host-group.sh)
fi

./server-add-host.sh
./server-add-trapper-host.sh

if [ $to_logout = 1 ]; then
    ./logout.sh
fi

