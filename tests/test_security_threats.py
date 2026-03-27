import os
import tempfile

from fastapi.testclient import TestClient

import api.app as api_app_module
from api.app import app
from engine.services import resolve_upload_file


def _write_temp_arxml(xml_text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".arxml")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    return path


def test_malformed_xml_returns_parse_fail():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES>")
    try:
        client = TestClient(app)
        resp = client.post("/audit", json={"file_path": file_path})
        assert resp.status_code == 200
        rows = resp.json().get("result", [])
        assert rows
        assert rows[0].get("name") == "Parse"
        assert rows[0].get("status") == "FAIL"
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def test_oversized_payload_rejected():
    client = TestClient(app)
    old_limit = api_app_module.MAX_REQUEST_BYTES
    api_app_module.MAX_REQUEST_BYTES = 8
    try:
        big_body = b'{"file_path":"' + (b"a" * 128) + b'"}'
        resp = client.post(
            "/audit",
            data=big_body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(big_body))},
        )
        assert resp.status_code == 413
        body = resp.json()
        assert body.get("error") == "REQUEST_TOO_LARGE"
    finally:
        api_app_module.MAX_REQUEST_BYTES = old_limit


def test_resolve_upload_file_blocks_traversal_name():
    upload_dir = tempfile.mkdtemp()
    try:
        out = resolve_upload_file(upload_dir, "..\\..\\secret.arxml")
        assert out == "..\\..\\secret.arxml"
    finally:
        # best-effort cleanup
        try:
            os.rmdir(upload_dir)
        except OSError:
            pass

