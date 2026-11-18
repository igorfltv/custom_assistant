"""Serve the built apps and the real API against a disposable browser-test database."""
import json
import os
import sys
import tempfile
from pathlib import Path

import uvicorn
from cryptography.fernet import Fernet
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def fixture_response(stage, connection, system, text, image=None):
    payload = json.loads(text)
    if "реестр ПРЕДСТАВЛЕННЫХ" in system:
        result = {"documents": []}
    elif "segments" in payload:
        segment = payload["segments"][0]
        observations = [
            {"key": key, "entity": "P1" if key.startswith("goods.") else None, "value": value, "quote": quote,
             "document_id": segment["document_id"], "locator": segment["locator"]}
            for key, value, quote in [
                ("goods.description", "Pump P1", "Pump P1"),
                ("goods.gross_weight", "100", "100 kg"),
                ("declarant.name", "QA Company", "QA Company"),
            ]
        ]
        result = {"kind": "invoice", "summary": "Pump P1", "observations": observations}
    elif "поисковые запросы" in system:
        result = {"queries": []}
    else:
        raise AssertionError("Missing synthetic model response")
    return result, {"provider": stage["provider"], "model": stage["model"], "seconds": 0, "usage": {}}


if __name__ == "__main__":
    port = int(os.environ["FORMA_QA_PORT"])
    with tempfile.TemporaryDirectory(prefix="forma-browser-") as folder:
        os.environ.update(DATABASE_URL="sqlite:///" + str(Path(folder) / "test.db"),
                          DATA_DIR=folder, ENCRYPTION_KEY=Fernet.generate_key().decode(),
                          SYNC_JOBS="true", PUBLIC_ORIGIN=f"http://127.0.0.1:{port}",
                          COOKIE_SECURE="false", ADMIN_EMAIL="qa@example.test",
                          ADMIN_PASSWORD=os.environ["FORMA_QA_PASSWORD"])
        from app import analysis
        from app.main import app

        analysis.complete = fixture_response
        for name in ("workspace", "admin", "landing"):
            prefix = "/" if name == "landing" else "/" + name
            app.mount(prefix, StaticFiles(directory=ROOT / name / "dist", html=True))
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
