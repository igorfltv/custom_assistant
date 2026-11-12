#!/usr/bin/env bash
set -euo pipefail
# Source and secrets travel separately. No GitHub token is copied to the VM.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
SSH_HOST="${SSH_HOST:-filatov@89.232.170.118}"
SSH_KEY="${SSH_KEY:-/Users/igorfilatov/cloud_ru_vm/id_rsa}"
SSH_KNOWN_HOSTS="${SSH_KNOWN_HOSTS:-/Users/igorfilatov/cloud_ru_vm/known_hosts}"
REMOTE_DIR="${REMOTE_DIR:-/home/filatov/forma}"
[[ "$SSH_HOST" =~ ^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+$ ]] || { echo 'Invalid SSH_HOST' >&2; exit 1; }
[[ "$REMOTE_DIR" =~ ^/[a-zA-Z0-9/_-]+$ ]] || { echo 'Invalid REMOTE_DIR' >&2; exit 1; }
CONTROL_DIR="$(mktemp -d /tmp/forma-ssh.XXXXXX)"
SSH_ARGS=(-4 -o BatchMode=yes -o IPQoS=none -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=2 -o ControlMaster=auto -o ControlPersist=120 -o "ControlPath=$CONTROL_DIR/master" -o "UserKnownHostsFile=$SSH_KNOWN_HOSTS" -i "$SSH_KEY")
cleanup() {
  ssh "${SSH_ARGS[@]}" -O exit "$SSH_HOST" 2>/dev/null || true
  rmdir "$CONTROL_DIR" 2>/dev/null || true
}
trap cleanup EXIT
if [[ -f .gitmodules ]]; then git submodule update --init --recursive; fi
for attempt in 1 2 3; do
  if ssh "${SSH_ARGS[@]}" "$SSH_HOST" true; then break; fi
  [[ "$attempt" -lt 3 ]] || exit 1
  echo "Retrying SSH connection ($attempt/3)…" >&2
done
ssh "${SSH_ARGS[@]}" "$SSH_HOST" bash -s < scripts/bootstrap-server.sh
RELEASE_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RELEASE_DIR="$REMOTE_DIR/releases/$RELEASE_ID"
ssh "${SSH_ARGS[@]}" "$SSH_HOST" "mkdir -p '$RELEASE_DIR'"
COPYFILE_DISABLE=1 tar --no-xattrs --exclude='.git' --exclude='.env' --exclude='.release.env' --exclude='.local' --exclude='node_modules' --exclude='.venv' --exclude='dist' --exclude='data' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='*.tsbuildinfo' -czf - . |
  ssh "${SSH_ARGS[@]}" "$SSH_HOST" "tar -xzf - -C '$RELEASE_DIR'"
ssh "${SSH_ARGS[@]}" "$SSH_HOST" bash -s -- "$REMOTE_DIR" "$RELEASE_DIR" <<'REMOTE'
set -euo pipefail
SHARED_DIR="$1"
RELEASE_DIR="$2"
cd "$RELEASE_DIR"
printf 'RELEASE_TAG=%s\n' "${RELEASE_DIR##*/}" > .release.env
compose() { sudo -n docker compose --env-file .env --env-file .release.env -p forma "$@"; }
if [[ -f "$SHARED_DIR/.env" ]]; then
  ln -s "$SHARED_DIR/.env" .env
else
  python3 scripts/init-env.py
  mv .env "$SHARED_DIR/.env"
  mkdir -p "$SHARED_DIR/.local"
  chmod 700 "$SHARED_DIR/.local"
  mv .local/admin-credentials.txt "$SHARED_DIR/.local/admin-credentials.txt"
  ln -s "$SHARED_DIR/.env" .env
fi
PREVIOUS="$(readlink "$SHARED_DIR/current" || true)"
rollback() {
  if [[ -n "$PREVIOUS" && -f "$PREVIOUS/compose.yaml" ]]; then
    echo 'Health check failed; restoring previous application release.' >&2
    cd "$PREVIOUS"
    compose up -d --wait --wait-timeout 180 || true
  fi
}
compose config --quiet
sudo -n env COMPOSE_PARALLEL_LIMIT=2 docker compose --env-file .env --env-file .release.env -p forma build
trap rollback ERR
compose up -d --wait --wait-timeout 180
python3 scripts/smoke.py
ln -sfn "$RELEASE_DIR" "$SHARED_DIR/current"
trap - ERR
REMOTE
printf '\nDeployment verified. Open the SSH tunnel with scripts/tunnel.sh.\n'
