#!/bin/bash

export ZBLAMB_FRONTEND_HNAME=${ZBLAMB_FRONTEND_HNAME:?'Frontend IP or DNS name must be specified'}
export ZBLAMB_PROXY_IP=${ZBLAMB_PROXY_IP:?'Server-reachable Proxy IP must be specified'}

# LOCAL IP for host creation -- Zabbix v5.4 needs it in API call
if [ -z $ZBLAMB_AGENT_IP ]; then
    IMDS_TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 10")
    export ZBLAMB_AGENT_IP=$(curl -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" http://169.254.169.254/latest/meta-data/local-ipv4)
fi

export ZBLAMB_TOKEN=$(./get-cred.sh)
export ZBLAMB_PROXY_ID=$(./server-add-proxy.sh)
export ZBLAMB_GROUP_ID=$(./server-add-host-group.sh)
./server-add-host.sh
./server-add-trapper-host.sh
./logout.sh

