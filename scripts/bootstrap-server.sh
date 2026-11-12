#!/usr/bin/env bash
set -euo pipefail
if command -v docker >/dev/null && sudo -n docker compose version >/dev/null 2>&1; then exit 0; fi
source /etc/os-release
[[ "$ID" == ubuntu ]] || { echo 'Automatic bootstrap supports Ubuntu only.' >&2; exit 1; }
if command -v docker >/dev/null; then
  echo 'Existing Docker has no Compose plugin. Install the matching plugin without replacing Docker.' >&2
  exit 1
fi
sudo -n apt-get update -qq
sudo -n apt-get install -y ca-certificates curl
sudo -n install -m 0755 -d /etc/apt/keyrings
sudo -n curl --fail --silent --show-error --location https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo -n chmod a+r /etc/apt/keyrings/docker.asc
ARCH="$(dpkg --print-architecture)"
printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: %s\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' "${UBUNTU_CODENAME:-$VERSION_CODENAME}" "$ARCH" |
  sudo -n tee /etc/apt/sources.list.d/docker.sources >/dev/null
sudo -n apt-get update -qq
sudo -n apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo -n systemctl enable --now docker
