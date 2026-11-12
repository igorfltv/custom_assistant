#!/usr/bin/env python3
from pathlib import Path
import urllib.request
import json

root = Path(__file__).resolve().parents[1]
values = dict(line.split("=", 1) for line in (root/".env").read_text().splitlines() if line and not line.startswith("#"))
url = "http://127.0.0.1:"+values.get("APP_PORT", "18761")
for path in ["/", "/workspace/", "/admin/", "/api/health"]:
    with urllib.request.urlopen(url+path, timeout=20) as response:
        assert response.status == 200
        if path == "/api/health":
            assert json.load(response)["status"] == "ok"
        else:
            assert b'root' in response.read()
    print("PASS", path)
