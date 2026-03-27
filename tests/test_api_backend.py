import os
import tempfile

from fastapi.testclient import TestClient

from api.app import app
from engine.services import run_full_audit


def _write_temp_arxml(xml_text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".arxml")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    return path


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "arxforge-api"


def test_audit_endpoint_matches_engine_service():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES/></AUTOSAR>")
    try:
        client = TestClient(app)
        api_resp = client.post("/audit", json={"file_path": file_path})
        assert api_resp.status_code == 200
        api_rows = api_resp.json()["result"]
        engine_rows = run_full_audit(file_path)
        assert len(api_rows) == len(engine_rows)
        assert [r.get("name") for r in api_rows] == [r.get("name") for r in engine_rows]
        assert [r.get("status") for r in api_rows] == [r.get("status") for r in engine_rows]
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

