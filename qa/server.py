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
        documents = []
        for segment in payload:
            if isinstance(segment, dict) and "REGISTER-QA" in segment.get("text", ""):
                documents = [{"kind": "certificate", "title": title, "number": number,
                              "locator": segment["locator"], "quote": title + " " + number}
                             for title, number in [("Certificate A", "AA-1"), ("Certificate B", "BB-2")]]
                break
        result = {"documents": documents}
    elif "segments" in payload:
        segment = payload["segments"][0]
        if "LEGAL-QA" in segment["text"]:
            from forma_declaration_agent import knowledge
            knowledge.index_snapshot(Path(os.environ["DATA_DIR"]),
                {"title": "Контрольный источник для проверки интерфейса", "url": "https://www.alta.ru/codex-2018/R3/GL17/ST106/"},
                "Контрольный пример. Сверьте массу с упаковочным листом. Конец примера.", "browser-fixture", "2026-11-20")
        observations = [
            {"key": key, "entity": "P1" if key.startswith("goods.") else None, "value": value, "quote": quote,
             "document_id": segment["document_id"], "locator": segment["locator"]}
            for key, value, quote in [
                ("goods.description", "Pump P1", "Pump P1"),
                ("goods.gross_weight", "100", "100 kg"),
                ("declarant.name", "QA Company", "QA Company"),
            ]
        ]
        if "REGISTER-QA" in segment["text"] and "Valve P2" in segment["text"]:
            observations.append({"key": "goods.description", "entity": "P2", "value": "Valve P2", "quote": "Valve P2",
                                 "document_id": segment["document_id"], "locator": segment["locator"]})
        if "Currency options: EUR / USD" in segment["text"]:
            for currency in ("EUR", "USD"):
                observations.append({"key": "currency", "value": currency, "quote": "Currency options: EUR / USD",
                                     "document_id": segment["document_id"], "locator": segment["locator"]})
        result = {"kind": "invoice", "summary": "Pump P1", "observations": observations}
    elif "Ты сопоставляешь товарные строки" in system:
        result = {"summary": "Две строки инвойса", "groups": [{"entities": [row["id"]]} for row in payload]}
    elif "поисковые запросы" in system:
        result = {"queries": []}
    elif isinstance(payload, dict) and "legal_sources" in payload:
        source = next((s for s in payload["legal_sources"] if s["sha256"] == "browser-fixture"), None)
        targeted = any(e.get("filename") == "LEGAL-QA.txt" for f in payload["fields"] for p in f["parts"] for e in p["sources"])
        result = {"findings": [{"item":1, "graph":"35", "topic":"documents", "message":"Сверьте основание массы брутто.",
                  "needed_inputs":["Упаковочный лист"], "quote":"Сверьте массу с упаковочным листом.",
                  "source_id":source["source_id"]}] if source and targeted else []}
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
