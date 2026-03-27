import os
import tempfile

from validators.audit_runner import run_audit_validators
from validators.xml_loader import parse_arxml_root


def _write_temp_arxml(xml_text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".arxml")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    return path


def test_parse_arxml_root_streaming_forced():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES><AR-PACKAGE><SHORT-NAME>Root</SHORT-NAME></AR-PACKAGE></AR-PACKAGES></AUTOSAR>")
    try:
        root = parse_arxml_root(file_path, prefer_streaming=True)
        assert root is not None
        assert "AUTOSAR" in str(root.tag)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def test_audit_runner_with_streaming_env_enabled():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES/></AUTOSAR>")
    prev_enabled = os.getenv("ARXFORGE_USE_STREAMING_PARSE")
    prev_min = os.getenv("ARXFORGE_STREAMING_PARSE_MIN_BYTES")
    os.environ["ARXFORGE_USE_STREAMING_PARSE"] = "true"
    os.environ["ARXFORGE_STREAMING_PARSE_MIN_BYTES"] = "0"
    try:
        rows = run_audit_validators(file_path, xsd_path="D:/does/not/exist.xsd")
        assert rows
        assert isinstance(rows, list)
        assert any(r.get("name") == "Data consistency" for r in rows)
    finally:
        if prev_enabled is None:
            os.environ.pop("ARXFORGE_USE_STREAMING_PARSE", None)
        else:
            os.environ["ARXFORGE_USE_STREAMING_PARSE"] = prev_enabled
        if prev_min is None:
            os.environ.pop("ARXFORGE_STREAMING_PARSE_MIN_BYTES", None)
        else:
            os.environ["ARXFORGE_STREAMING_PARSE_MIN_BYTES"] = prev_min
        if os.path.exists(file_path):
            os.remove(file_path)

