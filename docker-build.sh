#!/bin/bash -uxv

# scriptの絶対パス
SCRIPT_DIR=$(cd $(dirname $0); pwd)
pushd ${SCRIPT_DIR}

docker build -t annofab-cli docker/
