"""
Detect duplicate ports in ARXML: same (port_type, port_name, interface_path) appearing more than once.
"""
from typing import List, Tuple
from collections import defaultdict


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


def find_duplicate_ports(root) -> List[str]:
    """
    Find ports where the same (port_type, port_name, interface_path) appears more than once.
    Returns list of human-readable messages for each duplicate group.
    """
    # Collect every occurrence: key (port_type, name, interface) -> list of (parent_path_or_empty)
    key_to_count = defaultdict(int)
    key_examples = {}  # (port_type, name, interface) -> one full repr for message

    for elem in root.iter():
        tag = _local_tag(elem)
        if tag not in ("P-PORT-PROTOTYPE", "R-PORT-PROTOTYPE"):
            continue
        port_type = "P-PORT" if tag == "P-PORT-PROTOTYPE" else "R-PORT"
        name = _child_text(elem, "SHORT-NAME", "").strip() or "N/A"
        ref_path = ""
        for child in elem:
            ctag = _local_tag(child)
            if ctag in ("PROVIDED-INTERFACE-TREF", "REQUIRED-INTERFACE-TREF"):
                ref_path = (child.text or "").strip()
                break
        key = (port_type, name, ref_path)
        key_to_count[key] += 1
        if key not in key_examples:
            key_examples[key] = (port_type, name, ref_path)

    errors = []
    for key, count in key_to_count.items():
        if count <= 1:
            continue
        port_type, name, iface = key_examples[key]
        msg = f"Duplicate port: {port_type} '{name}' -> {iface or 'N/A'} ({count} occurrences)"
        errors.append(msg)
    return errors
