import os
import tempfile

from validators.audit_runner import run_audit_validators
from validators.plugins.builtin_audit import get_plugins_from_mapping
from validators.plugins.registry import discover_plugins
from validators.result_cache import clear_cache


def _write_temp_arxml(xml_text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".arxml")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    return path


def test_builtin_plugin_contract_from_mapping():
    mapping = {
        "validate_data_consistency_tool": lambda: {"status": "PASS"},
        "validate_port_references_tool": lambda: {"status": "PASS"},
    }
    plugins = get_plugins_from_mapping(mapping)
    assert len(plugins) == 2
    assert plugins[0].id == "validate_data_consistency_tool"
    assert callable(plugins[0].run)


def test_plugin_discovery_returns_list():
    plugins = discover_plugins()
    assert isinstance(plugins, list)


def test_audit_runner_plugin_mode_parity():
    file_path = _write_temp_arxml("<AUTOSAR><AR-PACKAGES/></AUTOSAR>")
    prev_plugin = os.getenv("ARXFORGE_USE_PLUGIN_VALIDATORS")
    prev_cache = os.getenv("ARXFORGE_ENABLE_AUDIT_CACHE")
    os.environ["ARXFORGE_ENABLE_AUDIT_CACHE"] = "false"
    try:
        clear_cache()
        os.environ["ARXFORGE_USE_PLUGIN_VALIDATORS"] = "false"
        rows_off = run_audit_validators(file_path, xsd_path="D:/does/not/exist.xsd")
        clear_cache()
        os.environ["ARXFORGE_USE_PLUGIN_VALIDATORS"] = "true"
        rows_on = run_audit_validators(file_path, xsd_path="D:/does/not/exist.xsd")
        assert [r.get("name") for r in rows_off] == [r.get("name") for r in rows_on]
        assert [r.get("status") for r in rows_off] == [r.get("status") for r in rows_on]
    finally:
        if prev_plugin is None:
            os.environ.pop("ARXFORGE_USE_PLUGIN_VALIDATORS", None)
        else:
            os.environ["ARXFORGE_USE_PLUGIN_VALIDATORS"] = prev_plugin
        if prev_cache is None:
            os.environ.pop("ARXFORGE_ENABLE_AUDIT_CACHE", None)
        else:
            os.environ["ARXFORGE_ENABLE_AUDIT_CACHE"] = prev_cache
        if os.path.exists(file_path):
            os.remove(file_path)

