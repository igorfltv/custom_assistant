#!/usr/bin/env bash
set -euo pipefail
exec ssh -4 -N -o ExitOnForwardFailure=yes -o BatchMode=yes -o IPQoS=none -o ConnectTimeout=60 -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=2 \
  -o "UserKnownHostsFile=${SSH_KNOWN_HOSTS:-/Users/igorfilatov/cloud_ru_vm/known_hosts}" \
  -i "${SSH_KEY:-/Users/igorfilatov/cloud_ru_vm/id_rsa}" \
  -L "${TUNNEL_PORT:-18761}:127.0.0.1:${REMOTE_PORT:-18761}" "${SSH_HOST:-filatov@89.232.170.118}"
