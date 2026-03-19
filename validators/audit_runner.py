"""
Run the full set of audit validators and return structured results for dashboard/CLI.
Returns list of {name, status, summary} where status is PASS, FAIL, or WARNING.
"""
import os
import xml.etree.ElementTree as ET
from typing import Any

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


def _status_from_errors(errors: list, name: str) -> tuple[str, str]:
    """Map list of error strings to (PASS|FAIL|WARNING, one-line summary)."""
    if not errors:
        return ("PASS", "No issues")
    text = " ".join(errors).lower()
    if "deprecated" in text or "optional" in text:
        return ("WARNING", errors[0][:80] + ("..." if len(errors[0]) > 80 else ""))
    return ("FAIL", errors[0][:80] + ("..." if len(errors[0]) > 80 else ""))


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
        return [{"name": "File", "status": "FAIL", "summary": f"File not found: {file_path}"}]

    root = None
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        return [{"name": "Parse", "status": "FAIL", "summary": f"Invalid ARXML: {e}"}]
    except Exception as e:
        return [{"name": "Parse", "status": "FAIL", "summary": str(e)}]

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_xsd = os.path.join(project_root, "AUTOSAR_schema.xsd")
    xsd_path = xsd_path or default_xsd

    # Schema (file-based)
    try:
        if os.path.isfile(xsd_path):
            is_valid, schema_errors = validate_arxml_schema(file_path, xsd_path)
            if is_valid:
                results.append({"name": "Schema", "status": "PASS", "summary": "Valid"})
            else:
                msg = schema_errors[0][:80] if schema_errors else "Validation failed"
                results.append({"name": "Schema", "status": "FAIL", "summary": msg})
        else:
            results.append({"name": "Schema", "status": "WARNING", "summary": "XSD not found; skipped"})
    except Exception as e:
        results.append({"name": "Schema", "status": "FAIL", "summary": str(e)[:80]})

    # Data consistency (detailed)
    try:
        report = validate_data_detailed(root)
        all_passed = all(
            report[k]["passed"]
            for k in ("uuid", "references", "base_type_refs", "port_interface_refs")
        )
        if all_passed:
            results.append({"name": "Data consistency", "status": "PASS", "summary": "All checks passed"})
        else:
            parts = [k for k in ("uuid", "references", "base_type_refs", "port_interface_refs") if not report[k]["passed"]]
            results.append({"name": "Data consistency", "status": "FAIL", "summary": f"Issues: {', '.join(parts)}"})
    except Exception as e:
        results.append({"name": "Data consistency", "status": "FAIL", "summary": str(e)[:80]})

    # Port references
    try:
        status = get_port_reference_status(root)
        broken = status.get("broken", [])
        if not broken:
            results.append({"name": "Port references", "status": "PASS", "summary": "All valid"})
        else:
            results.append({"name": "Port references", "status": "FAIL", "summary": f"{len(broken)} broken reference(s)"})
    except Exception as e:
        results.append({"name": "Port references", "status": "FAIL", "summary": str(e)[:80]})

    # Component references
    try:
        errs = validate_component_references(root)
        st, summary = _status_from_errors(errs, "Component references")
        results.append({"name": "Component references", "status": st, "summary": summary})
    except Exception as e:
        results.append({"name": "Component references", "status": "FAIL", "summary": str(e)[:80]})

    # Duplicate UUIDs
    try:
        errs, _ = validate_uuid_uniqueness(root)
        st, summary = _status_from_errors(errs, "Duplicate UUIDs")
        results.append({"name": "Duplicate UUIDs", "status": st, "summary": summary})
    except Exception as e:
        results.append({"name": "Duplicate UUIDs", "status": "FAIL", "summary": str(e)[:80]})

    # Duplicate ports
    try:
        errs = find_duplicate_ports(root)
        st, summary = _status_from_errors(errs, "Duplicate ports")
        results.append({"name": "Duplicate ports", "status": st, "summary": summary})
    except Exception as e:
        results.append({"name": "Duplicate ports", "status": "FAIL", "summary": str(e)[:80]})

    # Version compatibility
    try:
        errs = validate_autosar_version(root)
        if not errs:
            results.append({"name": "Version compatibility", "status": "PASS", "summary": "Supported"})
        else:
            text = " ".join(errs).lower()
            if "unsupported" in text:
                results.append({"name": "Version compatibility", "status": "FAIL", "summary": errs[0][:80]})
            else:
                results.append({"name": "Version compatibility", "status": "WARNING", "summary": errs[0][:80]})
    except Exception as e:
        results.append({"name": "Version compatibility", "status": "FAIL", "summary": str(e)[:80]})

    # SWC checks
    try:
        errs = validate_swc_checks(root)
        st, summary = _status_from_errors(errs, "SWC")
        results.append({"name": "SWC validation", "status": st, "summary": summary})
    except Exception as e:
        results.append({"name": "SWC validation", "status": "FAIL", "summary": str(e)[:80]})

    # Communication
    try:
        errs = []
        errs.extend(validate_pdu_definitions(root))
        errs.extend(validate_signal_to_pdu_mapping(root))
        errs.extend(validate_com_module(root))
        st, summary = _status_from_errors(errs, "Communication")
        results.append({"name": "Communication", "status": st, "summary": summary})
    except Exception as e:
        results.append({"name": "Communication", "status": "FAIL", "summary": str(e)[:80]})

    # Memory
    try:
        errs = []
        errs.extend(check_memory_overuse(root))
        errs.extend(validate_mem_map_usage(root))
        errs.extend(check_memory_segment_allocation(root))
        st, summary = _status_from_errors(errs, "Memory")
        results.append({"name": "Memory", "status": st, "summary": summary})
    except Exception as e:
        results.append({"name": "Memory", "status": "FAIL", "summary": str(e)[:80]})

    # RTE
    try:
        errs = []
        errs.extend(validate_rte_event_mappings(root))
        errs.extend(validate_synchronization_points(root))
        errs.extend(validate_port_interface_consistency(root))
        st, summary = _status_from_errors(errs, "RTE")
        results.append({"name": "RTE", "status": st, "summary": summary})
    except Exception as e:
        results.append({"name": "RTE", "status": "FAIL", "summary": str(e)[:80]})

    # Diagnostics
    try:
        errs = []
        errs.extend(validate_dtc_uniqueness(root))
        errs.extend(validate_dem_event_mappings(root))
        errs.extend(validate_dem_event_references(root))
        st, summary = _status_from_errors(errs, "Diagnostics")
        results.append({"name": "Diagnostics", "status": st, "summary": summary})
    except Exception as e:
        results.append({"name": "Diagnostics", "status": "FAIL", "summary": str(e)[:80]})

    # ECU/BSW
    try:
        errs = []
        errs.extend(validate_ecu_extract_references(root))
        errs.extend(validate_bsw_module_configurations(root))
        errs.extend(validate_ecu_bsw_alignment(root))
        st, summary = _status_from_errors(errs, "ECU/BSW")
        results.append({"name": "ECU/BSW", "status": st, "summary": summary})
    except Exception as e:
        results.append({"name": "ECU/BSW", "status": "FAIL", "summary": str(e)[:80]})

    return results
