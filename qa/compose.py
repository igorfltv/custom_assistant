"""Exercise the gateway, PostgreSQL, uploads, Redis and the RQ worker in disposable containers."""
import base64
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

import httpx


def main():
    root = Path(__file__).resolve().parents[1]
    project = "forma-qa-" + secrets.token_hex(6)
    password = secrets.token_urlsafe(24)
    env = dict(os.environ, APP_PORT="0", RELEASE_TAG=project, ADMIN_EMAIL="qa@example.test",
               ADMIN_PASSWORD=password, POSTGRES_PASSWORD=secrets.token_hex(24),
               ENCRYPTION_KEY=base64.urlsafe_b64encode(os.urandom(32)).decode(),
               COOKIE_SECURE="false", PUBLIC_ORIGIN="http://localhost")
    compose = ["docker", "compose", "-f", str(root / "compose.yaml"), "--env-file", os.devnull, "-p", project]

    def run(*args, capture=False):
        return subprocess.run([*compose, *args], cwd=root, env=env, check=True, text=True,
                              stdout=subprocess.PIPE if capture else None)

    try:
        run("build", "backend", "landing", "workspace", "admin")
        # The knowledge crawler has its own tests and would fetch external sites.
        run("up", "-d", "--no-build", "--wait", "--wait-timeout", "180", "gateway", "worker")
        base_url = "http://" + run("port", "gateway", "8080", capture=True).stdout.strip()
        subprocess.run([sys.executable, str(root / "scripts/smoke.py"), "--base-url", base_url], check=True)
        with httpx.Client(base_url=base_url, trust_env=False, timeout=20) as client:
            assert client.get("/api/declarations").status_code == 401
            client.post("/api/auth/login", json={"email": env["ADMIN_EMAIL"], "password": password}).raise_for_status()
            client.put("/api/admin/providers/deepseek", json={
                "base_url": "https://api.deepseek.com/v1", "api_key": "synthetic-queue-test",
            }).raise_for_status()
            shipment = client.post("/api/declarations", json={"title": "QA queue recovery"})
            shipment.raise_for_status()
            path = "/api/declarations/" + shipment.json()["id"]
            # A truncated document fails during parsing, before any model call.
            payload = b"An incomplete QA document"
            upload = client.post(path + "/documents", files={"file": ("incomplete.pdf", payload)})
            upload.raise_for_status()
            document = "/api/documents/" + upload.json()["id"] + "/download"
            assert client.get(document).content == payload
            job = client.post(path + "/analyze")
            assert job.status_code == 202, job.text
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                progress = client.get(path + "/progress")
                progress.raise_for_status()
                if progress.json()["status"] == "error":
                    break
                time.sleep(0.3)
            else:
                raise RuntimeError("Worker did not finish the invalid document within 60 seconds")
            detail = client.get(path).json()
            assert detail["run_id"] == job.json()["run_id"]
            assert detail["runs"][0]["status"] == "failed" and not detail["runs"][0]["calls"]
            assert detail["documents"][0]["status"] == "error" and not detail["xml_draft_available"]
            client.delete(path).raise_for_status()
            assert client.get(document).status_code == 404
            client.post("/api/auth/logout").raise_for_status()
            assert client.get("/api/declarations").status_code == 401
        print("PASS PostgreSQL, document storage, worker failure recovery and logout", flush=True)
    finally:
        run("down", "--volumes")
        for name in ("backend", "landing", "workspace", "admin"):
            tag = f"forma-{name}:{project}"
            if subprocess.run(["docker", "image", "inspect", tag], capture_output=True).returncode == 0:
                subprocess.run(["docker", "image", "rm", tag], check=True)


if __name__ == "__main__":
    main()
