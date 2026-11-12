#!/usr/bin/env bash
set -euo pipefail
# Publish the existing deployment; no application source is rebuilt or uploaded.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
SSH_HOST="${SSH_HOST:-filatov@89.232.170.118}"
SSH_KEY="${SSH_KEY:-/Users/igorfilatov/cloud_ru_vm/id_rsa}"
SSH_KNOWN_HOSTS="${SSH_KNOWN_HOSTS:-/Users/igorfilatov/cloud_ru_vm/known_hosts}"
REMOTE_DIR="${REMOTE_DIR:-/home/filatov/forma}"
PUBLIC_HOST="${PUBLIC_HOST:-89.232.170.118}"
[[ "$SSH_HOST" =~ ^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+$ ]] || exit 1
[[ "$REMOTE_DIR" =~ ^/[a-zA-Z0-9/_-]+$ ]] || exit 1
python3 -c 'import ipaddress,sys; ip=ipaddress.ip_address(sys.argv[1]); assert ip.version == 4 and ip.is_global' "$PUBLIC_HOST"
CONTROL_DIR="$(mktemp -d /tmp/forma-public.XXXXXX)"
SSH_ARGS=(-4 -o BatchMode=yes -o IPQoS=none -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=2 -o ControlMaster=auto -o ControlPersist=120 -o "ControlPath=$CONTROL_DIR/master" -o "UserKnownHostsFile=$SSH_KNOWN_HOSTS" -i "$SSH_KEY")
cleanup() {
  ssh "${SSH_ARGS[@]}" -O exit "$SSH_HOST" 2>/dev/null || true
  rmdir "$CONTROL_DIR" 2>/dev/null || true
}
trap cleanup EXIT
for attempt in 1 2 3; do
  if ssh "${SSH_ARGS[@]}" "$SSH_HOST" true; then break; fi
  [[ "$attempt" -lt 3 ]] || exit 1
done
ssh "${SSH_ARGS[@]}" "$SSH_HOST" "test -f '$REMOTE_DIR/current/compose.yaml' && mkdir -p '$REMOTE_DIR/public'"
COPYFILE_DISABLE=1 tar --no-xattrs -C deploy/public -czf - compose.yaml Caddyfile |
  ssh "${SSH_ARGS[@]}" "$SSH_HOST" "tar -xzf - -C '$REMOTE_DIR/public'"
ssh "${SSH_ARGS[@]}" "$SSH_HOST" bash -s -- "$REMOTE_DIR" "$PUBLIC_HOST" <<'REMOTE'
set -euo pipefail
SHARED_DIR="$1"
PUBLIC_HOST="$2"
cd "$SHARED_DIR/public"
printf 'PUBLIC_HOST=%s\n' "$PUBLIC_HOST" > .env
sudo -n docker network inspect forma_default >/dev/null
sudo -n docker compose config --quiet
sudo -n docker compose pull edge
sudo -n docker compose run --rm --no-deps -T edge caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile </dev/null

# Keep the database, keys, users, and selected providers intact.
python3 - "$SHARED_DIR" "$PUBLIC_HOST" <<'PY'
from pathlib import Path
import os, sys, time
root, host = Path(sys.argv[1]), sys.argv[2]
path = root / '.env'
content = path.read_text()
values = dict(line.split('=', 1) for line in content.splitlines() if line and not line.startswith('#'))
desired = {'PUBLIC_ORIGIN': 'http://' + host, 'COOKIE_SECURE': 'false'}
if any(values.get(key) != value for key, value in desired.items()):
    backup = root / '.local' / ('env-before-public-' + str(time.time_ns()))
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output: output.write(content)
    lines = [line for line in content.splitlines() if line.split('=',1)[0] not in desired]
    lines += [key+'='+value for key,value in desired.items()]
    temporary = root / '.env.public.tmp'
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as output: output.write('\n'.join(lines)+'\n')
    temporary.replace(path)
credentials = root / '.local/admin-credentials.txt'
if credentials.exists():
    text = credentials.read_text().splitlines()
    credentials.write_text('\n'.join('URL: http://'+host+'/admin/' if line.startswith('URL: ') else line for line in text)+'\n')
    credentials.chmod(0o600)
print('Configured public HTTP origin; existing data preserved')
PY
cd "$SHARED_DIR/current"
sudo -n docker compose --env-file .env --env-file .release.env -p forma up -d --no-deps --wait --wait-timeout 180 backend worker knowledge-sync
cd "$SHARED_DIR/public"
sudo -n docker compose up -d --force-recreate --wait edge
REMOTE

python3 scripts/smoke.py --base-url "http://$PUBLIC_HOST"
printf '\nPublic site: http://%s/\nWorkspace: http://%s/workspace/\nAdmin: http://%s/admin/\n' "$PUBLIC_HOST" "$PUBLIC_HOST" "$PUBLIC_HOST"
