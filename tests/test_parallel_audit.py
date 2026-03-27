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


def test_parallel_and_sequential_audit_have_same_order_and_status():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES/></AUTOSAR>")
    prev_parallel = os.getenv("ARXFORGE_ENABLE_PARALLEL_AUDIT")
    prev_workers = os.getenv("ARXFORGE_AUDIT_MAX_WORKERS")
    prev_cache = os.getenv("ARXFORGE_ENABLE_AUDIT_CACHE")
    os.environ["ARXFORGE_ENABLE_AUDIT_CACHE"] = "false"
    try:
        os.environ["ARXFORGE_ENABLE_PARALLEL_AUDIT"] = "false"
        os.environ["ARXFORGE_AUDIT_MAX_WORKERS"] = "1"
        clear_cache()
        rows_seq = run_audit_validators(file_path, xsd_path="D:/does/not/exist.xsd")

        os.environ["ARXFORGE_ENABLE_PARALLEL_AUDIT"] = "true"
        os.environ["ARXFORGE_AUDIT_MAX_WORKERS"] = "4"
        clear_cache()
        rows_par = run_audit_validators(file_path, xsd_path="D:/does/not/exist.xsd")

        assert [r.get("name") for r in rows_seq] == [r.get("name") for r in rows_par]
        assert [r.get("status") for r in rows_seq] == [r.get("status") for r in rows_par]
    finally:
        if prev_parallel is None:
            os.environ.pop("ARXFORGE_ENABLE_PARALLEL_AUDIT", None)
        else:
            os.environ["ARXFORGE_ENABLE_PARALLEL_AUDIT"] = prev_parallel
        if prev_workers is None:
            os.environ.pop("ARXFORGE_AUDIT_MAX_WORKERS", None)
        else:
            os.environ["ARXFORGE_AUDIT_MAX_WORKERS"] = prev_workers
        if prev_cache is None:
            os.environ.pop("ARXFORGE_ENABLE_AUDIT_CACHE", None)
        else:
            os.environ["ARXFORGE_ENABLE_AUDIT_CACHE"] = prev_cache
        if os.path.exists(file_path):
            os.remove(file_path)

