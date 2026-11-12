#!/usr/bin/env python3
"""Generate credentials once. Never echo them or replace existing configuration."""
import base64
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
env = root / ".env"
if env.exists():
    print("Existing .env preserved")
else:
    password = secrets.token_urlsafe(30)
    port = os.environ.get("APP_PORT", "18761")
    if not port.isdigit() or not 1024 <= int(port) <= 65535:
        raise SystemExit("APP_PORT must be an unprivileged TCP port")
    content = {
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "ADMIN_EMAIL": "admin@forma.local", "ADMIN_PASSWORD": password,
        "APP_PORT": port, "PUBLIC_ORIGIN": "http://localhost:"+port, "COOKIE_SECURE":"false",
    }
    descriptor = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write("\n".join(k+"="+v for k,v in content.items())+"\n")
    private = root / ".local"
    private.mkdir(mode=0o700, exist_ok=True)
    path = private / "admin-credentials.txt"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write("URL: "+content["PUBLIC_ORIGIN"]+"/admin/\nEmail: "+content["ADMIN_EMAIL"]+"\nPassword: "+password+"\n")
    print("Created .env and .local/admin-credentials.txt (0600)")
