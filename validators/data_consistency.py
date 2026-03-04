import xml.etree.ElementTree as ET
from typing import List, Tuple, Set, Dict, Any


def _local_tag(elem):
    """Return local tag name without namespace."""
    if elem is None or not elem.tag:
        return ""
    return elem.tag.split("}", 1)[1] if "}" in elem.tag else elem.tag


def _child_text(elem, local_name, default=""):
    """Get text of first child with given local tag name (any namespace)."""
    if elem is None:
        return default
    for child in elem:
        if _local_tag(child) == local_name and child.text:
            return child.text.strip()
    return default


def _get_attr(elem, attr_name):
    """Get attribute value by local name (handles namespaced attributes)."""
    v = elem.attrib.get(attr_name)
    if v:
        return v
    for key in elem.attrib:
        if key == attr_name or key.endswith("}" + attr_name):
            return elem.attrib[key]
    return ""


def _build_path_set(root):
    """Build set of full paths (e.g. /Package/SubPackage/Name) using only SHORT-NAME segments to match AUTOSAR *-TREF paths."""
    paths = set()

    def _path_from_ancestors(elem, parent_path):
        name = _child_text(elem, "SHORT-NAME")
        if name:
            current = f"{parent_path}/{name}" if parent_path else "/" + name
            paths.add(current)
        else:
            current = parent_path
        for child in elem:
            _path_from_ancestors(child, current)

    _path_from_ancestors(root, "")
    return paths


# AUTOSAR interface element types that PROVIDED/REQUIRED-INTERFACE-TREF can point to
_INTERFACE_TAGS = (
    "CLIENT-SERVER-INTERFACE",
    "SENDER-RECEIVER-INTERFACE",
    "PARAMETER-INTERFACE",
    "MODE-SWITCH-INTERFACE",
    "NV-INTERFACE",
    "TRIGGER-INTERFACE",
)


def _build_interface_path_set(root):
    """Build set of paths only for elements that are actual interface definitions.
    Port refs (PROVIDED/REQUIRED-INTERFACE-TREF) must point to one of these."""
    paths = set()

    def _path_from_ancestors(elem, parent_path):
        name = _child_text(elem, "SHORT-NAME")
        if name:
            current = f"{parent_path}/{name}" if parent_path else "/" + name
            if _local_tag(elem) in _INTERFACE_TAGS:
                paths.add(current)
        else:
            current = parent_path
        for child in elem:
            _path_from_ancestors(child, current)

    _path_from_ancestors(root, "")
    return paths


def validate_uuid_uniqueness(root):
    """Ensures all UUIDs are unique. Returns (errors, uuid_count)."""
    uuids = {}
    errors = []
    count = 0
    for elem in root.iter():
        uuid_val = _get_attr(elem, "UUID")
        if not uuid_val:
            continue
        count += 1
        if uuid_val in uuids:
            errors.append(f"⚠️ Duplicate UUID found: {uuid_val}")
        else:
            uuids[uuid_val] = _local_tag(elem)
    return errors, count

def validate_required_attributes(root, required_attributes):
    """Ensures all required attributes are present in the ARXML file."""
    errors = []

    for elem in root.iter():
        for attr in required_attributes:
            if attr not in elem.attrib:
                element_name = elem.tag
                errors.append(f"⚠️ Missing required attribute '{attr}' in element <{element_name}>")

    return errors

def validate_referenced_elements(root):
    """Ensures REFERENCE attributes point to valid ID. Returns (errors, ref_count)."""
    existing_ids = set()
    for elem in root.iter():
        id_val = _get_attr(elem, "ID")
        if id_val:
            existing_ids.add(id_val)
    errors = []
    ref_count = 0
    for elem in root.iter():
        ref = _get_attr(elem, "REFERENCE")
        if not ref:
            continue
        ref_count += 1
        if ref not in existing_ids:
            errors.append(f"⚠️ Broken reference: {ref} not found in the ARXML file.")
    return errors, ref_count


def validate_base_type_refs(root):
    """Ensures BASE-TYPE-REF point to existing elements. Returns (errors, count)."""
    paths = _build_path_set(root)
    paths_normalized = {_normalize_path(p) for p in paths}
    errors = []
    count = 0
    for elem in root.iter():
        if _local_tag(elem) != "BASE-TYPE-REF":
            continue
        ref_path = (elem.text or "").strip()
        if not ref_path:
            continue
        count += 1
        if _normalize_path(ref_path) not in paths_normalized:
            errors.append(f"⚠️ Base type reference not found: {ref_path}")
    return errors, count


def _normalize_path(path):
    """Normalize a path for comparison (ensure leading slash, no trailing slash)."""
    if not path:
        return ""
    p = (path or "").strip()
    if p and not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/") or "/"


def validate_port_interface_refs(root):
    """Ensures PROVIDED/REQUIRED-INTERFACE-TREF point to existing interface definitions. Returns (errors, count)."""
    paths = _build_interface_path_set(root)
    paths_normalized = {_normalize_path(p) for p in paths}
    errors = []
    count = 0
    for elem in root.iter():
        tag = _local_tag(elem)
        if tag not in ("PROVIDED-INTERFACE-TREF", "REQUIRED-INTERFACE-TREF"):
            continue
        ref_path = (elem.text or "").strip()
        if not ref_path:
            continue
        count += 1
        if _normalize_path(ref_path) not in paths_normalized:
            errors.append(f"⚠️ Interface reference not found: {ref_path}")
    return errors, count


def get_port_reference_status(root):
    """Returns which port prototypes have valid vs broken interface references.
    Only paths to actual interface elements (CLIENT-SERVER-INTERFACE, SENDER-RECEIVER-INTERFACE, etc.) are considered defined.
    Returns {"valid": [(port_type, port_name, interface_path), ...], "broken": [(port_type, port_name, interface_path), ...]}.
    """
    paths = _build_interface_path_set(root)
    paths_normalized = {_normalize_path(p) for p in paths}
    valid = []
    broken = []
    for elem in root.iter():
        tag = _local_tag(elem)
        if tag not in ("P-PORT-PROTOTYPE", "R-PORT-PROTOTYPE"):
            continue
        port_type = "P-PORT" if tag == "P-PORT-PROTOTYPE" else "R-PORT"
        port_name = _child_text(elem, "SHORT-NAME") or "N/A"
        ref_path = ""
        for child in elem:
            ctag = _local_tag(child)
            if ctag == "PROVIDED-INTERFACE-TREF" or ctag == "REQUIRED-INTERFACE-TREF":
                ref_path = (child.text or "").strip()
                break
        if not ref_path:
            continue
        if _normalize_path(ref_path) in paths_normalized:
            valid.append((port_type, port_name, ref_path))
        else:
            broken.append((port_type, port_name, ref_path))
    return {"valid": valid, "broken": broken}


def validate_data(root):
    """Runs data consistency checks; returns flat list of errors (backward compatible)."""
    errors = []
    errs, _ = validate_uuid_uniqueness(root)
    errors.extend(errs)
    errs, _ = validate_referenced_elements(root)
    errors.extend(errs)
    errs, _ = validate_base_type_refs(root)
    errors.extend(errs)
    errs, _ = validate_port_interface_refs(root)
    errors.extend(errs)
    return errors


def validate_data_detailed(root):
    """Runs all data consistency checks and returns a detailed report for summary output."""
    uuid_errors, uuid_count = validate_uuid_uniqueness(root)
    ref_errors, ref_count = validate_referenced_elements(root)
    base_errors, base_count = validate_base_type_refs(root)
    port_errors, port_count = validate_port_interface_refs(root)
    return {
        "uuid": {"passed": len(uuid_errors) == 0, "count": uuid_count, "errors": uuid_errors},
        "references": {"passed": len(ref_errors) == 0, "checked": ref_count, "errors": ref_errors},
        "base_type_refs": {"passed": len(base_errors) == 0, "checked": base_count, "errors": base_errors},
        "port_interface_refs": {"passed": len(port_errors) == 0, "checked": port_count, "errors": port_errors},
    }
