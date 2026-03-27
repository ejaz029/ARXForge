import os
import tempfile

from ai.agent_tools import check_duplicate_uuids_tool
from ai.arxml_agent import _build_validation_coverage, ENGINE_VERSION, RESULT_SCHEMA_VERSION
from tests.test_utils import run_tool
from validators.audit_runner import run_audit_validators


def _write_temp_arxml(xml_text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".arxml")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    return path


def test_duplicate_uuid_check_no_uuid_file_returns_no_duplicates():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES/></AUTOSAR>")
    try:
        result = run_tool(check_duplicate_uuids_tool, file_path=file_path)
        assert "No duplicate UUIDs found" in result
        assert "Duplicate UUIDs found" not in result
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def test_validation_coverage_has_explicit_skips():
    coverage = _build_validation_coverage(
        [{"tool_name": "validate_data_consistency_tool", "result": "✅ Data consistency validation passed.", "error": False}]
    )
    by_id = {row["validator_id"]: row for row in coverage}
    assert by_id["validate_data_consistency_tool"]["status"] == "PASS"
    assert by_id["validate_schema_tool"]["status"] == "SKIPPED"
    assert "Not executed by plan" in by_id["validate_schema_tool"]["reason"]


def test_audit_runner_rows_include_schema_and_engine_versions():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES/></AUTOSAR>")
    try:
        rows = run_audit_validators(file_path, xsd_path="D:/does/not/exist.xsd")
        assert rows, "Audit should return rows"
        for row in rows:
            assert row.get("engine_version") == ENGINE_VERSION
            assert row.get("result_schema_version") == RESULT_SCHEMA_VERSION
            assert "validator_id" in row
            assert "issues" in row
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

