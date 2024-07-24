#!/bin/bash

if [ $# -lt 2 ]; then
    TRANSFORM_FN="multi_trigger_transform"
else
    TRANSFORM_FN=$1
fi

cp functions/utils/utils.py functions/$TRANSFORM_FN/
cp functions/utils/requirements.txt functions/$TRANSFORM_FN/

sam build -t metric-stream.yaml

rm functions/$TRANSFORM_FN/utils.py functions/$TRANSFORM_FN/requirements.txt