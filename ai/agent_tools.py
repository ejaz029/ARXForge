"""
LangChain tool wrappers for ARXML validation and analysis functions.
These tools enable the AI agent to autonomously select and execute validation tasks.
"""
import os
import xml.etree.ElementTree as ET
from typing import Optional
from langchain_core.tools import tool

# Import existing validation functions
from ai.arxml_extractor import extract_arxml_data, _local_tag, _child_text
from validators.extract_ports import extract_ports_from_arxml
from validators.schema_validation import validate_arxml_schema
from validators.data_consistency import (
    validate_uuid_uniqueness,
    validate_required_attributes,
    validate_referenced_elements,
    validate_data,
    validate_data_detailed,
    get_port_reference_status,
)
from validators.swc_checks import (
    check_swc_definitions,
    check_runnable_entities,
    check_port_data_types,
    validate_swc_checks
)
from validators.communication_checks import (
    validate_pdu_definitions,
    validate_signal_to_pdu_mapping,
    validate_com_module
)
from validators.memory_checks import (
    check_memory_overuse,
    validate_mem_map_usage,
    check_memory_segment_allocation
)
from validators.rte_checks import (
    validate_rte_event_mappings,
    validate_synchronization_points,
    validate_port_interface_consistency
)
from validators.diagnostic_checks import (
    validate_dtc_uniqueness,
    validate_dem_event_mappings,
    validate_dem_event_references
)
from validators.ecu_bsw_checks import (
    validate_ecu_extract_references,
    validate_bsw_module_configurations,
    validate_ecu_bsw_alignment
)
from validators.version_compatibility import (
    extract_autosar_version,
    check_autosar_version,
    check_deprecated_elements,
    validate_autosar_version
)
from validators.component_ref_checks import validate_component_references
from validators.duplicates import find_duplicate_ports


def _parse_arxml_file(file_path: str) -> Optional[ET.Element]:
    """Helper function to parse ARXML file and return root element."""
    try:
        if not os.path.exists(file_path):
            return None
        tree = ET.parse(file_path)
        return tree.getroot()
    except Exception:
        return None


@tool
def extract_software_components(file_path: str) -> str:
    """Extract all software components (SWC) from an ARXML file.
    
    Args:
        file_path: Path to the ARXML file to analyze
        
    Returns:
        Formatted string listing all software components found
    """
    try:
        data = extract_arxml_data(file_path)
        if "error" in data:
            return f"❌ Error: {data['error']}"
        
        components = data.get("swc_components", [])
        base_types = data.get("base_types", [])
        impl_types = data.get("implementation_data_types", [])
        
        if not components and not base_types and not impl_types:
            return f"ℹ️ No software components, base types, or implementation data types found in {os.path.basename(file_path)}"
        
        parts = []
        # Summary line: SWC count plus base types / implementation data types when present
        summary_parts = [f"{len(components)} software component(s)"]
        if base_types:
            summary_parts.append(f"{len(base_types)} base types")
        if impl_types:
            summary_parts.append(f"{len(impl_types)} implementation data types")
        parts.append("📋 Summary: " + ", ".join(summary_parts) + ".")
        
        if components:
            parts.append(f"📄 Software Components ({len(components)}):\n" + "\n".join(f"{i}. {c}" for i, c in enumerate(components, 1)))
        if base_types:
            parts.append(f"📄 Base Types ({len(base_types)}):\n" + "\n".join(f"{i}. {b.get('name', '')} (category: {b.get('category', '')})" for i, b in enumerate(base_types, 1)))
        if impl_types:
            parts.append(f"📄 Implementation Data Types ({len(impl_types)}):\n" + "\n".join(f"{i}. {d.get('name', '')} (base: {d.get('base_type_ref', '')})" for i, d in enumerate(impl_types, 1)))
        
        return "\n\n".join(parts)
    except Exception as e:
        return f"❌ Error extracting software components: {str(e)}"


@tool
def extract_ports_tool(file_path: str) -> str:
    """Extract all P-PORTs and R-PORTs from an ARXML file.
    
    Args:
        file_path: Path to the ARXML file to analyze
        
    Returns:
        Formatted string listing all ports with their types and interfaces
    """
    try:
        ports = extract_ports_from_arxml(file_path)
        if not ports or (ports and "error" in ports[0]):
            error_msg = ports[0].get("error", "Unknown error") if ports else "No ports found"
            return f"❌ {error_msg}"
        
        p_ports = [p for p in ports if p.get('port_type') == 'P-PORT']
        r_ports = [p for p in ports if p.get('port_type') == 'R-PORT']
        
        result = f"📄 Ports in {os.path.basename(file_path)}:\n"
        result += f"🔷 Total: {len(ports)} (P-PORTs: {len(p_ports)}, R-PORTs: {len(r_ports)})\n\n"
        
        if p_ports:
            result += "🔌 P-PORTs (Provided Interfaces):\n"
            for i, p in enumerate(p_ports, 1):
                result += f"{i}. {p.get('name', 'N/A')} - Interface: {p.get('interface', 'N/A')}\n"
        
        if r_ports:
            result += "\n🔌 R-PORTs (Required Interfaces):\n"
            for i, p in enumerate(r_ports, 1):
                result += f"{i}. {p.get('name', 'N/A')} - Interface: {p.get('interface', 'N/A')}\n"
        
        return result
    except Exception as e:
        return f"❌ Error extracting ports: {str(e)}"


@tool
def extract_ecu_instances(file_path: str) -> str:
    """Extract all ECU instances from an ARXML file.
    
    Args:
        file_path: Path to the ARXML file to analyze
        
    Returns:
        Formatted string listing all ECU instances with their UUIDs
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        
        ecu_instances = []
        for elem in root.iter():
            tag = _local_tag(elem)
            # AUTOSAR uses both ECU (e.g. in CANCatalog/ECUs) and ECU-INSTANCE
            if tag not in ("ECU", "ECU-INSTANCE"):
                continue
            name = _child_text(elem, "SHORT-NAME") or "Unknown"
            uuid = elem.attrib.get("UUID", "N/A")
            ecu_instances.append((name, uuid))
        
        if not ecu_instances:
            return f"ℹ️ No ECU instances found in {os.path.basename(file_path)}"
        
        result = f"📄 ECU Instances in {os.path.basename(file_path)}:\n"
        for i, (name, uuid) in enumerate(ecu_instances, 1):
            result += f"{i}. {name} (UUID: {uuid})\n"
        return result
    except Exception as e:
        return f"❌ Error extracting ECU instances: {str(e)}"


def _get_uuid_from_elem(elem) -> Optional[str]:
    """Get UUID from element, handling namespaced attribute."""
    u = elem.attrib.get("UUID")
    if u:
        return u
    for key in elem.attrib:
        if key.endswith("UUID") or key == "UUID":
            return elem.attrib[key]
    return None


@tool
def extract_uuids_tool(file_path: str) -> str:
    """Extract and list all UUIDs present in an ARXML file with their element context.
    
    Args:
        file_path: Path to the ARXML file to analyze
        
    Returns:
        Formatted string listing each element that has a UUID (tag/name and UUID value)
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        
        entries = []
        for elem in root.iter():
            uuid_val = _get_uuid_from_elem(elem)
            if not uuid_val:
                continue
            tag = _local_tag(elem)
            name = _child_text(elem, "SHORT-NAME") or ""
            entries.append((tag, name, uuid_val))
        
        if not entries:
            return f"ℹ️ No elements with UUID attribute found in {os.path.basename(file_path)}"
        
        lines = [f"📄 UUIDs in {os.path.basename(file_path)} ({len(entries)} total):"]
        for i, (tag, name, uuid_val) in enumerate(entries, 1):
            label = f"{tag}: {name}" if name else tag
            lines.append(f"{i}. {label}\n   UUID: {uuid_val}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error extracting UUIDs: {str(e)}"


@tool
def check_duplicate_uuids_tool(file_path: str) -> str:
    """Check for duplicate UUIDs within an ARXML file.
    
    Args:
        file_path: Path to the ARXML file to analyze
        
    Returns:
        Report of duplicate UUIDs found, or confirmation of uniqueness
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        
        errors = validate_uuid_uniqueness(root)
        if not errors:
            return f"✅ No duplicate UUIDs found in {os.path.basename(file_path)}"
        
        result = f"❌ Duplicate UUIDs found in {os.path.basename(file_path)}:\n"
        for error in errors:
            result += f"  {error}\n"
        return result
    except Exception as e:
        return f"❌ Error checking duplicate UUIDs: {str(e)}"


@tool
def validate_schema_tool(arxml_file: str, xsd_file: Optional[str] = None) -> str:
    """Validate ARXML file against AUTOSAR XSD schema.
    
    Args:
        arxml_file: Path to the ARXML file to validate
        xsd_file: Path to XSD schema file (defaults to AUTOSAR_schema.xsd in project root)
        
    Returns:
        Validation result with any schema errors found
    """
    try:
        if xsd_file is None:
            # Default to AUTOSAR_schema.xsd in project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            xsd_file = os.path.join(project_root, "AUTOSAR_schema.xsd")
        
        if not os.path.exists(xsd_file):
            return f"❌ XSD schema file not found: {xsd_file}"
        
        is_valid, errors = validate_arxml_schema(arxml_file, xsd_file)
        if is_valid:
            return f"✅ Schema validation passed for {os.path.basename(arxml_file)}"
        
        result = f"❌ Schema validation failed for {os.path.basename(arxml_file)}:\n"
        for error in errors:
            result += f"  {error}\n"
        return result
    except Exception as e:
        return f"❌ Error during schema validation: {str(e)}"


@tool
def validate_data_consistency_tool(file_path: str) -> str:
    """Run data consistency validation checks on ARXML file.
    Checks UUID uniqueness, reference integrity, base type refs, and port/interface refs.
    
    Args:
        file_path: Path to the ARXML file to validate
        
    Returns:
        Detailed report of data consistency validation (per-check results and counts)
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        
        report = validate_data_detailed(root)
        filename = os.path.basename(file_path)
        lines = [f"📋 Data consistency validation: {filename}", ""]
        
        # 1. UUID uniqueness
        u = report["uuid"]
        status = "✅" if u["passed"] else "❌"
        lines.append(f"1. UUID uniqueness: {status}")
        lines.append(f"   Found {u['count']} element(s) with UUID; all unique." if u["passed"] else f"   Found {u['count']} element(s) with UUID.")
        for err in u["errors"][:10]:
            lines.append(f"   {err}")
        if len(u["errors"]) > 10:
            lines.append(f"   ... and {len(u['errors']) - 10} more.")
        lines.append("")
        
        # 2. Reference integrity (ID/REFERENCE)
        r = report["references"]
        status = "✅" if r["passed"] else "❌"
        lines.append(f"2. Reference integrity: {status}")
        lines.append(f"   Checked {r['checked']} reference(s)." + (" All valid." if r["passed"] else ""))
        for err in r["errors"][:10]:
            lines.append(f"   {err}")
        if len(r["errors"]) > 10:
            lines.append(f"   ... and {len(r['errors']) - 10} more.")
        lines.append("")
        
        # 3. Base type references
        b = report["base_type_refs"]
        status = "✅" if b["passed"] else "❌"
        lines.append(f"3. Base type references: {status}")
        lines.append(f"   Checked {b['checked']} BASE-TYPE-REF(s)." + (" All point to existing types." if b["passed"] else ""))
        for err in b["errors"][:10]:
            lines.append(f"   {err}")
        if len(b["errors"]) > 10:
            lines.append(f"   ... and {len(b['errors']) - 10} more.")
        lines.append("")
        
        # 4. Port / interface references
        p = report["port_interface_refs"]
        status = "✅" if p["passed"] else "❌"
        lines.append(f"4. Port interface references: {status}")
        lines.append(f"   Checked {p['checked']} interface reference(s)." + (" All valid." if p["passed"] else ""))
        for err in p["errors"][:10]:
            lines.append(f"   {err}")
        if len(p["errors"]) > 10:
            lines.append(f"   ... and {len(p['errors']) - 10} more.")
        
        all_passed = all(
            report[k]["passed"]
            for k in ("uuid", "references", "base_type_refs", "port_interface_refs")
        )
        lines.append("")
        lines.append("✅ Data consistency validation passed." if all_passed else "❌ Data consistency issues found (see above).")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error during data consistency validation: {str(e)}"


@tool
def validate_port_references_tool(file_path: str) -> str:
    """Check if all referenced ports (P-PORT and R-PORT) have valid interface references.
    Use this when the user asks: are ports properly defined, are required interfaces missing,
    check interface references, or validate that port interfaces exist.
    
    Args:
        file_path: Path to the ARXML file to validate
        
    Returns:
        Report listing which port references are valid and which are broken (interface not found).
        If any references are broken, required interfaces are missing.
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        
        status = get_port_reference_status(root)
        valid = status["valid"]
        broken = status["broken"]
        filename = os.path.basename(file_path)
        all_ok = len(broken) == 0

        lines = [f"📋 Port reference validation: {filename}", ""]
        lines.append("Required interfaces missing: Yes." if not all_ok else "Required interfaces missing: No.")
        lines.append("")
        if not valid and not broken:
            lines.append("ℹ️ No port prototypes (P-PORT-PROTOTYPE / R-PORT-PROTOTYPE) found in the file.")
            return "\n".join(lines)

        total = len(valid) + len(broken)
        lines.append(f"Checked {total} port(s). " + ("All referenced interfaces are properly defined." if all_ok else f"{len(broken)} broken reference(s) — required interfaces missing."))
        lines.append("")
        
        if valid:
            lines.append("✅ Properly defined port references:")
            for i, (ptype, pname, iface) in enumerate(valid[:20], 1):
                lines.append(f"  {i}. {ptype} '{pname}' → {iface}")
            if len(valid) > 20:
                lines.append(f"  ... and {len(valid) - 20} more.")
            lines.append("")
        
        if broken:
            lines.append("❌ Broken port references (interface not found at path):")
            for i, (ptype, pname, iface) in enumerate(broken, 1):
                lines.append(f"  {i}. {ptype} '{pname}' → {iface}")
            lines.append("")
        
        lines.append("✅ All referenced ports are properly defined." if all_ok else "❌ Not all referenced ports are properly defined. See broken references above.")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error validating port references: {str(e)}"


@tool
def validate_swc_tool(file_path: str) -> str:
    """Validate software component definitions, runnable entities, and port data types.
    
    Args:
        file_path: Path to the ARXML file to validate
        
    Returns:
        Report of software component validation results
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        
        errors = validate_swc_checks(root)
        if not errors:
            return f"✅ Software component validation passed for {os.path.basename(file_path)}"
        
        result = f"❌ Software component validation issues found in {os.path.basename(file_path)}:\n"
        for error in errors:
            result += f"  {error}\n"
        return result
    except Exception as e:
        return f"❌ Error during software component validation: {str(e)}"


@tool
def validate_communication_tool(file_path: str) -> str:
    """Validate PDU definitions, signal-to-PDU mappings, and COM module consistency.
    
    Args:
        file_path: Path to the ARXML file to validate
        
    Returns:
        Report of communication validation results
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        
        errors = []
        errors.extend(validate_pdu_definitions(root))
        errors.extend(validate_signal_to_pdu_mapping(root))
        errors.extend(validate_com_module(root))
        
        if not errors:
            return f"✅ Communication validation passed for {os.path.basename(file_path)}"
        
        result = f"❌ Communication validation issues found in {os.path.basename(file_path)}:\n"
        for error in errors:
            result += f"  {error}\n"
        return result
    except Exception as e:
        return f"❌ Error during communication validation: {str(e)}"


@tool
def validate_memory_tool(file_path: str, max_memory: int = 1024) -> str:
    """Validate memory usage, memory map usage, and memory segment allocation.
    
    Args:
        file_path: Path to the ARXML file to validate
        max_memory: Maximum allowed memory in KB (default: 1024)
        
    Returns:
        Report of memory validation results
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        
        errors = []
        errors.extend(check_memory_overuse(root, max_memory))
        errors.extend(validate_mem_map_usage(root))
        errors.extend(check_memory_segment_allocation(root))
        
        if not errors:
            return f"✅ Memory validation passed for {os.path.basename(file_path)}"
        
        result = f"❌ Memory validation issues found in {os.path.basename(file_path)}:\n"
        for error in errors:
            result += f"  {error}\n"
        return result
    except Exception as e:
        return f"❌ Error during memory validation: {str(e)}"


@tool
def validate_rte_tool(file_path: str) -> str:
    """Validate RTE event mappings, synchronization points, and port interface consistency.
    
    Args:
        file_path: Path to the ARXML file to validate
        
    Returns:
        Report of RTE validation results
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        
        errors = []
        errors.extend(validate_rte_event_mappings(root))
        errors.extend(validate_synchronization_points(root))
        errors.extend(validate_port_interface_consistency(root))
        
        if not errors:
            return f"✅ RTE validation passed for {os.path.basename(file_path)}"
        
        result = f"❌ RTE validation issues found in {os.path.basename(file_path)}:\n"
        for error in errors:
            result += f"  {error}\n"
        return result
    except Exception as e:
        return f"❌ Error during RTE validation: {str(e)}"


@tool
def validate_diagnostics_tool(file_path: str) -> str:
    """Validate DTC uniqueness, DEM event mappings, and DEM event references.
    
    Args:
        file_path: Path to the ARXML file to validate
        
    Returns:
        Report of diagnostics validation results
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        
        errors = []
        errors.extend(validate_dtc_uniqueness(root))
        errors.extend(validate_dem_event_mappings(root))
        errors.extend(validate_dem_event_references(root))
        
        if not errors:
            return f"✅ Diagnostics validation passed for {os.path.basename(file_path)}"
        
        result = f"❌ Diagnostics validation issues found in {os.path.basename(file_path)}:\n"
        for error in errors:
            result += f"  {error}\n"
        return result
    except Exception as e:
        return f"❌ Error during diagnostics validation: {str(e)}"


@tool
def validate_ecu_bsw_tool(file_path: str) -> str:
    """Validate ECU extract references, BSW module configurations, and ECU-BSW alignment.
    
    Args:
        file_path: Path to the ARXML file to validate
        
    Returns:
        Report of ECU/BSW validation results
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        
        errors = []
        errors.extend(validate_ecu_extract_references(root))
        errors.extend(validate_bsw_module_configurations(root))
        errors.extend(validate_ecu_bsw_alignment(root))
        
        if not errors:
            return f"✅ ECU/BSW validation passed for {os.path.basename(file_path)}"
        
        result = f"❌ ECU/BSW validation issues found in {os.path.basename(file_path)}:\n"
        for error in errors:
            result += f"  {error}\n"
        return result
    except Exception as e:
        return f"❌ Error during ECU/BSW validation: {str(e)}"


@tool
def validate_version_compatibility_tool(file_path: str) -> str:
    """Check AUTOSAR version compatibility and detect deprecated elements.
    
    Args:
        file_path: Path to the ARXML file to validate
        
    Returns:
        Report of version compatibility validation results
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        
        errors = validate_autosar_version(root)
        if not errors:
            version = extract_autosar_version(root)
            return f"✅ Version compatibility validation passed for {os.path.basename(file_path)} (AUTOSAR {version})"
        
        result = f"❌ Version compatibility issues found in {os.path.basename(file_path)}:\n"
        for error in errors:
            result += f"  {error}\n"
        return result
    except Exception as e:
        return f"❌ Error during version compatibility validation: {str(e)}"


@tool
def validate_component_refs_tool(file_path: str) -> str:
    """Check that all component references (e.g. COMPONENT-PROTOTYPE TYPE-TREF) point to
    defined software component types in the same file. Use when checking for undefined
    components or reporting inconsistencies.
    Args:
        file_path: Path to the ARXML file to validate
    Returns:
        Report listing any referenced component types that are not defined in the file.
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        errors = validate_component_references(root)
        filename = os.path.basename(file_path)
        if not errors:
            return f"✅ All component references are defined in {filename}"
        lines = [f"❌ Undefined component reference(s) in {filename}:", ""]
        for err in errors:
            lines.append(f"  {err}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error validating component references: {str(e)}"


@tool
def duplicate_ports_tool(file_path: str) -> str:
    """Check for duplicate ports in the ARXML file (same port name + interface appearing more than once).
    Use when the user asks which ports are duplicated, or whether there are duplicate ports.
    Args:
        file_path: Path to the ARXML file to check
    Returns:
        Report listing any duplicate ports, or confirmation that none were found.
    """
    try:
        root = _parse_arxml_file(file_path)
        if root is None:
            return f"❌ Error: Could not parse {os.path.basename(file_path)}"
        errors = find_duplicate_ports(root)
        filename = os.path.basename(file_path)
        if not errors:
            return f"✅ No duplicate ports found in {filename}. All ports have unique (name, interface) combinations."
        lines = [f"❌ Duplicate port(s) in {filename}:", ""]
        for err in errors:
            lines.append(f"  {err}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error checking duplicate ports: {str(e)}"


def get_all_tools():
    """Returns a list of all available agent tools."""
    return [
        extract_software_components,
        extract_ports_tool,
        extract_ecu_instances,
        extract_uuids_tool,
        check_duplicate_uuids_tool,
        validate_schema_tool,
        validate_data_consistency_tool,
        validate_port_references_tool,
        validate_swc_tool,
        validate_communication_tool,
        validate_memory_tool,
        validate_rte_tool,
        validate_diagnostics_tool,
        validate_ecu_bsw_tool,
        validate_version_compatibility_tool,
        validate_component_refs_tool,
        duplicate_ports_tool,
    ]


# Manual Tool Registry - maps tool names to tool instances
ALL_TOOLS = get_all_tools()
TOOL_REGISTRY = {
    tool.name: tool
    for tool in ALL_TOOLS
}

# Verify tool registry on import (only when DEBUG_AGENT is set)
def _debug_tools():
    try:
        import os
        import yaml
        debug = os.getenv("DEBUG_AGENT", "").lower() in ("1", "true", "yes")
        if not debug:
            try:
                with open("config.yaml", "r") as f:
                    cfg = yaml.safe_load(f) or {}
                debug = cfg.get("DEBUG_AGENT", False)
            except Exception:
                pass
        if debug:
            print("Registered tools:", list(TOOL_REGISTRY.keys()))
    except Exception:
        pass


if __name__ == "__main__":
    _debug_tools()
