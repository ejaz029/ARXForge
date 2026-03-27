import json
import os
import tempfile

from fastapi.testclient import TestClient

from api.app import app
from engine.report_export import export_audit_report
from validators.audit_runner import run_audit_validators


def _write_temp_arxml(xml_text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".arxml")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    return path


def test_export_json_and_md_artifacts():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES/></AUTOSAR>")
    out_dir = tempfile.mkdtemp()
    try:
        rows = run_audit_validators(file_path, xsd_path="D:/does/not/exist.xsd")
        trace = {
            "file": file_path,
            "total_duration_ms": 1.0,
            "pass_count": sum(1 for r in rows if r.get("status") == "PASS"),
            "fail_count": sum(1 for r in rows if r.get("status") == "FAIL"),
            "warning_count": sum(1 for r in rows if r.get("status") == "WARNING"),
            "validators": [],
        }
        json_path = os.path.join(out_dir, "report.json")
        md_path = os.path.join(out_dir, "report.md")
        j = export_audit_report(file_path=file_path, rows=rows, trace=trace, export_format="json", output_path=json_path)
        m = export_audit_report(file_path=file_path, rows=rows, trace=trace, export_format="md", output_path=md_path)
        assert os.path.exists(j["path"])
        assert os.path.exists(m["path"])
        with open(json_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        assert "results" in payload and "trace" in payload
    finally:
        for name in ("report.json", "report.md"):
            p = os.path.join(out_dir, name)
            if os.path.exists(p):
                os.remove(p)
        try:
            os.rmdir(out_dir)
        except OSError:
            pass
        if os.path.exists(file_path):
            os.remove(file_path)


def test_api_audit_export_returns_artifact():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES/></AUTOSAR>")
    out_dir = tempfile.mkdtemp()
    out_json = os.path.join(out_dir, "api_export.json")
    try:
        client = TestClient(app)
        resp = client.post(
            "/audit/export",
            json={
                "file_path": file_path,
                "xsd_path": "D:/does/not/exist.xsd",
                "export_format": "json",
                "output_path": out_json,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "artifact" in body
        assert body["artifact"]["format"] == "json"
        assert os.path.exists(body["artifact"]["path"])
    finally:
        if os.path.exists(out_json):
            os.remove(out_json)
        try:
            os.rmdir(out_dir)
        except OSError:
            pass
        if os.path.exists(file_path):
            os.remove(file_path)

