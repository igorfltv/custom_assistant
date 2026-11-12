#!/usr/bin/env python3
from pathlib import Path
import urllib.request
import json
import re
import time
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", help="Explicit deployment URL; HTTPS certificates are verified")
args = parser.parse_args()
if args.base_url:
    url = args.base_url.rstrip("/")
else:
    root = Path(__file__).resolve().parents[1]
    values = dict(line.split("=", 1) for line in (root/".env").read_text().splitlines() if line and not line.startswith("#"))
    url = "http://127.0.0.1:"+values.get("APP_PORT", "18761")
for path in ["/", "/workspace/", "/admin/", "/api/health"]:
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url+path, timeout=20) as response:
                assert response.status == 200
                if path == "/api/health":
                    assert json.load(response)["status"] == "ok"
                else:
                    html = response.read().decode()
                    assert 'id="root"' in html
                    assets = re.findall(r'(?:src|href)="([^"]+/assets/[^\"]+|/assets/[^\"]+)"', html)
                    assert assets, "No application assets found"
                    assert all(asset.startswith(path+"assets/") for asset in assets), "Wrong application routed to this path"
                    for asset in assets:
                        with urllib.request.urlopen(url+asset, timeout=20) as loaded:
                            assert loaded.status == 200
                            assert "text/html" not in loaded.headers.get("Content-Type", ""), "Asset returned HTML"
                            assert loaded.read(), "Empty application asset"
            print("PASS", path, "and application assets" if path != "/api/health" else "")
            break
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2)
