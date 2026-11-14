#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
command -v docker >/dev/null || { echo 'Install Docker with Compose first.' >&2; exit 1; }
docker compose version >/dev/null
docker info >/dev/null 2>&1 || { echo 'Start Docker before deployment.' >&2; exit 1; }
if [[ -f .gitmodules ]]; then
  git submodule update --init --recursive
fi
for component in backend agent landing workspace admin; do
  [[ -f "$component/README.md" ]] || { echo "Missing component: $component" >&2; exit 1; }
done
python3 scripts/init-env.py
docker compose config --quiet
docker compose build
docker compose up --detach --wait --wait-timeout 180
# Refresh the bind-mounted proxy configuration, including on an in-place upgrade.
docker compose up --detach --force-recreate --no-deps gateway
python3 scripts/smoke.py
printf '\nReady. Credentials: %s/.local/admin-credentials.txt\n' "$ROOT_DIR"
