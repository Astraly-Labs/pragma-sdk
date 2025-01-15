#!/bin/bash

set -euo pipefail

export INFISICAL_TOKEN=$(infisical login --method=universal-auth --client-id=${INFISICAL_CLIENT_ID} --client-secret=${INFISICAL_CLIENT_SECRET} --silent --plain)
infisical export  --projectId=${INFISICAL_PROJECT_ID} --env=${INFISICAL_ENV}  --path=${INFISICAL_APP_PATH} > .env
source .env

# Execute Stunnel
/usr/bin/stunnel stunnel.conf &

sleep 5

# Execute LMAX Connector
exec /opt/lmax-connector/.venv/bin/python3.12 -m lmax_connector
