import os
import tempfile

from validators.audit_runner import run_audit_validators
from validators.result_cache import clear_cache


def _write_temp_arxml(xml_text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".arxml")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    return path


def test_audit_cache_hit_returns_same_result():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES/></AUTOSAR>")
    prev = os.getenv("ARXFORGE_ENABLE_AUDIT_CACHE")
    os.environ["ARXFORGE_ENABLE_AUDIT_CACHE"] = "true"
    clear_cache()
    try:
        rows1 = run_audit_validators(file_path, xsd_path="D:/does/not/exist.xsd")
        rows2 = run_audit_validators(file_path, xsd_path="D:/does/not/exist.xsd")
        assert rows1 == rows2
        assert len(rows1) > 0
    finally:
        if prev is None:
            os.environ.pop("ARXFORGE_ENABLE_AUDIT_CACHE", None)
        else:
            os.environ["ARXFORGE_ENABLE_AUDIT_CACHE"] = prev
        if os.path.exists(file_path):
            os.remove(file_path)


def test_audit_cache_invalidation_on_file_change():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES/></AUTOSAR>")
    prev = os.getenv("ARXFORGE_ENABLE_AUDIT_CACHE")
    os.environ["ARXFORGE_ENABLE_AUDIT_CACHE"] = "true"
    clear_cache()
    try:
        rows1 = run_audit_validators(file_path, xsd_path="D:/does/not/exist.xsd")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("<AUTOSAR><AR-PACKAGES>")  # malformed on purpose
        rows2 = run_audit_validators(file_path, xsd_path="D:/does/not/exist.xsd")
        assert rows1 != rows2
        assert rows2 and rows2[0].get("name") == "Parse"
    finally:
        if prev is None:
            os.environ.pop("ARXFORGE_ENABLE_AUDIT_CACHE", None)
        else:
            os.environ["ARXFORGE_ENABLE_AUDIT_CACHE"] = prev
        if os.path.exists(file_path):
            os.remove(file_path)

