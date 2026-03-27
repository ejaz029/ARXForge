import os
import tempfile

from fastapi.testclient import TestClient

from api.app import app


def _write_temp_arxml(xml_text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".arxml")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    return path


def test_audit_api_returns_trace_object():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES/></AUTOSAR>")
    try:
        client = TestClient(app)
        resp = client.post("/audit", json={"file_path": file_path, "xsd_path": "D:/does/not/exist.xsd"})
        assert resp.status_code == 200
        body = resp.json()
        assert "result" in body
        assert "trace" in body
        trace = body["trace"]
        assert "file" in trace
        assert "total_duration_ms" in trace
        assert "pass_count" in trace
        assert "fail_count" in trace
        assert "warning_count" in trace
        assert "validators" in trace and isinstance(trace["validators"], list)
        if trace["validators"]:
            first = trace["validators"][0]
            assert {"validator_id", "name", "status", "duration_ms"}.issubset(set(first.keys()))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

