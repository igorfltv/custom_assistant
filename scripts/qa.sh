#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -gt 1 || ( $# -eq 1 && $1 != --compose ) ]]; then
  echo "Usage: $0 [--compose]" >&2
  exit 2
fi
uv run --directory agent --locked pytest -q
uv run --directory backend --locked pytest -q
npm ci --no-audit --no-fund
npm run build
PLAYWRIGHT_SKIP_BROWSER_GC=1 npx --no-install playwright install chromium --only-shell
npm run test:browser
if [[ ${1:-} == --compose ]]; then
  uv run --project backend --locked python qa/compose.py
fi
