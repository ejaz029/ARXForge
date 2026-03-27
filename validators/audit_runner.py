"""
Run the full set of audit validators and return structured results for dashboard/CLI.
Returns list of {name, status, summary} where status is PASS, FAIL, or WARNING.
"""
import os
import xml.etree.ElementTree as ET
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging
from validators.xml_loader import parse_arxml_root
from validators.result_cache import cache_key, file_sha256, get_cached, set_cached, xsd_fingerprint

from validators.schema_validation import validate_arxml_schema
from validators.data_consistency import (
    validate_data_detailed,
    get_port_reference_status,
)
from validators.component_ref_checks import validate_component_references
from validators.duplicates import find_duplicate_ports
from validators.data_consistency import validate_uuid_uniqueness
from validators.version_compatibility import validate_autosar_version
from validators.swc_checks import validate_swc_checks
from validators.communication_checks import (
    validate_pdu_definitions,
    validate_signal_to_pdu_mapping,
    validate_com_module,
)
from validators.memory_checks import (
    check_memory_overuse,
    validate_mem_map_usage,
    check_memory_segment_allocation,
)
from validators.rte_checks import (
    validate_rte_event_mappings,
    validate_synchronization_points,
    validate_port_interface_consistency,
)
from validators.diagnostic_checks import (
    validate_dtc_uniqueness,
    validate_dem_event_mappings,
    validate_dem_event_references,
)
from validators.ecu_bsw_checks import (
    validate_ecu_extract_references,
    validate_bsw_module_configurations,
    validate_ecu_bsw_alignment,
)
from validators.plugins.registry import discover_plugins
from validators.plugins.builtin_audit import get_plugins_from_mapping

ENGINE_VERSION = "1.0.0"
RESULT_SCHEMA_VERSION = "1.0.0"
AUDIT_VALIDATOR_SET_VERSION = "1.0.0"
logger = logging.getLogger("ARXForge.Audit")


def _status_from_errors(errors: list, name: str) -> tuple[str, str]:
    """Map list of error strings to (PASS|FAIL|WARNING, one-line summary)."""
    if not errors:
        return ("PASS", "No issues")
    text = " ".join(errors).lower()
    if "deprecated" in text or "optional" in text:
        return ("WARNING", errors[0][:80] + ("..." if len(errors[0]) > 80 else ""))
    return ("FAIL", errors[0][:80] + ("..." if len(errors[0]) > 80 else ""))


def _make_row(name: str, status: str, summary: str, validator_id: str, issues: list[dict] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "summary": summary,
        "validator_id": validator_id,
        "issues": issues or [],
        "engine_version": ENGINE_VERSION,
        "result_schema_version": RESULT_SCHEMA_VERSION,
    }


def run_audit_validators(
    file_path: str,
    xsd_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    Run all audit validators on the given ARXML file.
    Returns list of {"name": str, "status": "PASS"|"FAIL"|"WARNING", "summary": str}.
    """
    results: list[dict[str, Any]] = []
    if not os.path.isfile(file_path):
        return [_make_row("File", "FAIL", f"File not found: {file_path}", "file")]
    run_started = time.perf_counter()

    use_cache = os.getenv("ARXFORGE_ENABLE_AUDIT_CACHE", "true").strip().lower() in ("1", "true", "yes", "on")
    cache_token = None
    if use_cache:
        try:
            file_digest = file_sha256(file_path)
            cache_token = cache_key([
                "run_audit_validators",
                file_digest,
                xsd_fingerprint(xsd_path),
                ENGINE_VERSION,
                RESULT_SCHEMA_VERSION,
                AUDIT_VALIDATOR_SET_VERSION,
            ])
            cached = get_cached(cache_token)
            if cached is not None:
                return cached
        except Exception:
            # Cache should never break validation flow.
            cache_token = None

    root = None
    try:
        root = parse_arxml_root(file_path)
    except ET.ParseError as e:
        return [_make_row("Parse", "FAIL", f"Invalid ARXML: {e}", "parse")]
    except Exception as e:
        return [_make_row("Parse", "FAIL", str(e), "parse")]

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_xsd = os.path.join(project_root, "AUTOSAR_schema.xsd")
    xsd_path = xsd_path or default_xsd

    # Schema (file-based)
    try:
        if os.path.isfile(xsd_path):
            is_valid, schema_errors = validate_arxml_schema(file_path, xsd_path)
            if is_valid:
                results.append(_make_row("Schema", "PASS", "Valid", "validate_schema_tool"))
            else:
                msg = schema_errors[0][:80] if schema_errors else "Validation failed"
                results.append(_make_row("Schema", "FAIL", msg, "validate_schema_tool"))
        else:
            results.append(_make_row("Schema", "WARNING", "XSD not found; skipped", "validate_schema_tool"))
    except Exception as e:
        results.append(_make_row("Schema", "FAIL", str(e)[:80], "validate_schema_tool"))

    def _row_data_consistency():
        report = validate_data_detailed(root)
        all_passed = all(
            report[k]["passed"]
            for k in ("uuid", "references", "base_type_refs", "port_interface_refs")
        )
        if all_passed:
            return _make_row("Data consistency", "PASS", "All checks passed", "validate_data_consistency_tool")
        parts = [k for k in ("uuid", "references", "base_type_refs", "port_interface_refs") if not report[k]["passed"]]
        return _make_row("Data consistency", "FAIL", f"Issues: {', '.join(parts)}", "validate_data_consistency_tool")

    def _row_port_references():
        status = get_port_reference_status(root)
        broken = status.get("broken", [])
        if not broken:
            return _make_row("Port references", "PASS", "All valid", "validate_port_references_tool")
        return _make_row("Port references", "FAIL", f"{len(broken)} broken reference(s)", "validate_port_references_tool")

    def _row_component_references():
        errs = validate_component_references(root)
        st, summary = _status_from_errors(errs, "Component references")
        return _make_row("Component references", st, summary, "validate_component_refs_tool")

    def _row_duplicate_uuids():
        errs, _ = validate_uuid_uniqueness(root)
        st, summary = _status_from_errors(errs, "Duplicate UUIDs")
        return _make_row("Duplicate UUIDs", st, summary, "check_duplicate_uuids_tool")

    def _row_duplicate_ports():
        errs = find_duplicate_ports(root)
        st, summary = _status_from_errors(errs, "Duplicate ports")
        return _make_row("Duplicate ports", st, summary, "duplicate_ports_tool")

    def _row_version_compatibility():
        errs = validate_autosar_version(root)
        if not errs:
            return _make_row("Version compatibility", "PASS", "Supported", "validate_version_compatibility_tool")
        text = " ".join(errs).lower()
        if "unsupported" in text:
            return _make_row("Version compatibility", "FAIL", errs[0][:80], "validate_version_compatibility_tool")
        return _make_row("Version compatibility", "WARNING", errs[0][:80], "validate_version_compatibility_tool")

    def _row_swc():
        errs = validate_swc_checks(root)
        st, summary = _status_from_errors(errs, "SWC")
        return _make_row("SWC validation", st, summary, "validate_swc_tool")

    def _row_communication():
        errs = []
        errs.extend(validate_pdu_definitions(root))
        errs.extend(validate_signal_to_pdu_mapping(root))
        errs.extend(validate_com_module(root))
        st, summary = _status_from_errors(errs, "Communication")
        return _make_row("Communication", st, summary, "validate_communication_tool")

    def _row_memory():
        errs = []
        errs.extend(check_memory_overuse(root))
        errs.extend(validate_mem_map_usage(root))
        errs.extend(check_memory_segment_allocation(root))
        st, summary = _status_from_errors(errs, "Memory")
        return _make_row("Memory", st, summary, "validate_memory_tool")

    def _row_rte():
        errs = []
        errs.extend(validate_rte_event_mappings(root))
        errs.extend(validate_synchronization_points(root))
        errs.extend(validate_port_interface_consistency(root))
        st, summary = _status_from_errors(errs, "RTE")
        return _make_row("RTE", st, summary, "validate_rte_tool")

    def _row_diagnostics():
        errs = []
        errs.extend(validate_dtc_uniqueness(root))
        errs.extend(validate_dem_event_mappings(root))
        errs.extend(validate_dem_event_references(root))
        st, summary = _status_from_errors(errs, "Diagnostics")
        return _make_row("Diagnostics", st, summary, "validate_diagnostics_tool")

    def _row_ecu_bsw():
        errs = []
        errs.extend(validate_ecu_extract_references(root))
        errs.extend(validate_bsw_module_configurations(root))
        errs.extend(validate_ecu_bsw_alignment(root))
        st, summary = _status_from_errors(errs, "ECU/BSW")
        return _make_row("ECU/BSW", st, summary, "validate_ecu_bsw_tool")

    check_specs = [
        ("Data consistency", "validate_data_consistency_tool", _row_data_consistency),
        ("Port references", "validate_port_references_tool", _row_port_references),
        ("Component references", "validate_component_refs_tool", _row_component_references),
        ("Duplicate UUIDs", "check_duplicate_uuids_tool", _row_duplicate_uuids),
        ("Duplicate ports", "duplicate_ports_tool", _row_duplicate_ports),
        ("Version compatibility", "validate_version_compatibility_tool", _row_version_compatibility),
        ("SWC validation", "validate_swc_tool", _row_swc),
        ("Communication", "validate_communication_tool", _row_communication),
        ("Memory", "validate_memory_tool", _row_memory),
        ("RTE", "validate_rte_tool", _row_rte),
        ("Diagnostics", "validate_diagnostics_tool", _row_diagnostics),
        ("ECU/BSW", "validate_ecu_bsw_tool", _row_ecu_bsw),
    ]

    use_plugins = os.getenv("ARXFORGE_USE_PLUGIN_VALIDATORS", "true").strip().lower() in ("1", "true", "yes", "on")
    if use_plugins:
        run_by_id = {vid: fn for _name, vid, fn in check_specs}
        # Built-in plugins provide deterministic metadata/order over existing logic
        plugin_list = get_plugins_from_mapping(run_by_id)
        # Also allow external discovery modules to append/override by id if provided.
        discovered = discover_plugins()
        discovered_by_id = {p.id: p for p in discovered}
        merged = []
        for p in plugin_list:
            merged.append(discovered_by_id.get(p.id, p))
        # Append additional discovered plugins not in built-ins
        existing_ids = {p.id for p in merged}
        for p in discovered:
            if p.id not in existing_ids:
                merged.append(p)
        merged.sort(key=lambda p: (p.order, p.id))
        check_specs = [(p.name, p.id, p.run) for p in merged]

    parallel_enabled = os.getenv("ARXFORGE_ENABLE_PARALLEL_AUDIT", "true").strip().lower() in ("1", "true", "yes", "on")
    max_workers = max(1, int(os.getenv("ARXFORGE_AUDIT_MAX_WORKERS", "4")))
    rows_by_name: dict[str, dict[str, Any]] = {}

    trace_entries: list[dict[str, Any]] = []

    def _safe_run(name: str, validator_id: str, fn):
        t0 = time.perf_counter()
        try:
            row = fn()
            duration_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            trace_entries.append({
                "validator_id": validator_id,
                "name": name,
                "status": row.get("status", "UNKNOWN"),
                "duration_ms": duration_ms,
            })
            logger.info(
                "validator=%s file=%s status=%s duration_ms=%.3f",
                validator_id,
                os.path.basename(file_path),
                row.get("status", "UNKNOWN"),
                duration_ms,
            )
            return row
        except Exception as e:
            duration_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            trace_entries.append({
                "validator_id": validator_id,
                "name": name,
                "status": "FAIL",
                "duration_ms": duration_ms,
            })
            logger.exception(
                "validator=%s file=%s status=FAIL duration_ms=%.3f",
                validator_id,
                os.path.basename(file_path),
                duration_ms,
            )
            return _make_row(name, "FAIL", str(e)[:80], validator_id)

    if parallel_enabled and max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {
                pool.submit(_safe_run, name, validator_id, fn): (name, validator_id)
                for name, validator_id, fn in check_specs
            }
            for fut in as_completed(future_map):
                name, _validator_id = future_map[fut]
                rows_by_name[name] = fut.result()
    else:
        for name, validator_id, fn in check_specs:
            rows_by_name[name] = _safe_run(name, validator_id, fn)

    for name, _validator_id, _fn in check_specs:
        results.append(rows_by_name[name])

    total_duration_ms = round((time.perf_counter() - run_started) * 1000.0, 3)
    trace_by_id = {t["validator_id"]: t for t in trace_entries}
    for row in results:
        t = trace_by_id.get(row.get("validator_id"))
        if t is not None:
            row["duration_ms"] = t["duration_ms"]
    logger.info(
        "audit_complete file=%s validators=%d duration_ms=%.3f pass=%d fail=%d warning=%d",
        os.path.basename(file_path),
        len(results),
        total_duration_ms,
        sum(1 for r in results if r.get("status") == "PASS"),
        sum(1 for r in results if r.get("status") == "FAIL"),
        sum(1 for r in results if r.get("status") == "WARNING"),
    )

    if cache_token:
        try:
            set_cached(cache_token, results)
        except Exception:
            pass
    return results
