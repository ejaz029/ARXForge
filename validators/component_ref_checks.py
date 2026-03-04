"""
Validates that component references (e.g. COMPONENT-PROTOTYPE TYPE-TREF) point to
defined software component types in the same ARXML file.
"""
from typing import List

# Component type elements that can be referenced by COMPONENT-PROTOTYPE TYPE-TREF
_COMPONENT_TYPE_TAGS = (
    "APPLICATION-SOFTWARE-COMPONENT-TYPE",
    "COMPOSITION-SW-COMPONENT-TYPE",
    "ASSEMBLY-SW-COMPONENT-TYPE",
)


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


def _normalize_path(path: str) -> str:
    """Normalize path for comparison (leading slash, no trailing slash)."""
    if not path:
        return ""
    p = (path or "").strip()
    if p and not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/") or "/"


def _build_defined_component_path_set(root) -> set:
    """Build set of paths to defined component types (SWC definitions)."""
    paths = set()

    def _path_from_ancestors(elem, parent_path):
        name = _child_text(elem, "SHORT-NAME")
        if name:
            current = f"{parent_path}/{name}" if parent_path else "/" + name
            if _local_tag(elem) in _COMPONENT_TYPE_TAGS:
                paths.add(current)
        else:
            current = parent_path
        for child in elem:
            _path_from_ancestors(child, current)

    _path_from_ancestors(root, "")
    return paths


def validate_component_references(root) -> List[str]:
    """
    Check that every COMPONENT-PROTOTYPE TYPE-TREF points to a defined component type
    (APPLICATION-SOFTWARE-COMPONENT-TYPE, COMPOSITION-SW-COMPONENT-TYPE, or
    ASSEMBLY-SW-COMPONENT-TYPE) in this file.
    Returns list of error messages for undefined component references.
    """
    defined_paths = _build_defined_component_path_set(root)
    defined_normalized = {_normalize_path(p) for p in defined_paths}
    errors = []

    for elem in root.iter():
        if _local_tag(elem) != "COMPONENT-PROTOTYPE":
            continue
        ref_path = _child_text(elem, "TYPE-TREF", "").strip()
        if not ref_path:
            continue
        norm = _normalize_path(ref_path)
        if norm not in defined_normalized:
            comp_name = _child_text(elem, "SHORT-NAME", "?")
            errors.append(
                f"Referenced component type not defined in file: '{ref_path}' "
                f"(port/prototype: {comp_name})"
            )
    return errors
