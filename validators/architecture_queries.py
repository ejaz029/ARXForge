"""
Query layer for NL architecture questions: which SWCs use an interface, what depends on a signal/message.
Used by agent tools for natural-language architecture queries.
"""
import xml.etree.ElementTree as ET
from typing import List


def _local_tag(elem: ET.Element) -> str:
    if elem is None or not elem.tag:
        return ""
    return elem.tag.split("}", 1)[1] if "}" in elem.tag else elem.tag


def _child_text(elem: ET.Element, local_name: str, default: str = "") -> str:
    if elem is None:
        return default
    for child in elem:
        if _local_tag(child) == local_name and child.text:
            return child.text.strip()
    return default


def list_swcs_using_interface(root: ET.Element, interface_name: str) -> List[str]:
    """
    Return list of SWC/component short names that have a port referencing the given interface.
    interface_name is matched against the last segment of PROVIDED-INTERFACE-TREF / REQUIRED-INTERFACE-TREF.
    """
    if not interface_name or not interface_name.strip():
        return []
    interface_name = interface_name.strip()
    path_stack: List[tuple[str, str]] = []
    current_swc: str | None = None
    result: List[str] = []

    def visit(elem: ET.Element) -> None:
        nonlocal current_swc
        tag = _local_tag(elem)
        short_name = _child_text(elem, "SHORT-NAME")
        if tag in ("APPLICATION-SOFTWARE-COMPONENT-TYPE", "COMPONENT-PROTOTYPE", "COMPOSITION-SW-COMPONENT-TYPE") and short_name:
            path_stack.append((tag, short_name))
            current_swc = short_name
        if tag in ("P-PORT-PROTOTYPE", "R-PORT-PROTOTYPE"):
            ref = ""
            for child in elem:
                ctag = _local_tag(child)
                if ctag in ("PROVIDED-INTERFACE-TREF", "REQUIRED-INTERFACE-TREF"):
                    ref = (child.text or "").strip()
                    break
            if ref:
                last_seg = ref.strip("/").split("/")[-1]
                if last_seg == interface_name and current_swc and current_swc not in result:
                    result.append(current_swc)
        for child in elem:
            visit(child)
        if tag in ("APPLICATION-SOFTWARE-COMPONENT-TYPE", "COMPONENT-PROTOTYPE", "COMPOSITION-SW-COMPONENT-TYPE") and short_name:
            path_stack.pop()
            current_swc = path_stack[-1][1] if path_stack else None

    visit(root)
    return result


def list_dependents_of_signal_or_message(root: ET.Element, name: str) -> List[str]:
    """
    Return list of human-readable dependents: interface or SWC names that reference the given
    signal/message name (e.g. VARIABLE-DATA-PROTOTYPE SHORT-NAME or interface SHORT-NAME).
    We look for interfaces containing a VARIABLE-DATA-PROTOTYPE with this name, then SWCs
    that use those interfaces.
    """
    if not name or not name.strip():
        return []
    name = name.strip()
    # 1) Interfaces that define this signal (VARIABLE-DATA-PROTOTYPE with SHORT-NAME == name)
    defining_interfaces: List[str] = []
    for elem in root.iter():
        tag = _local_tag(elem)
        if tag not in ("SENDER-RECEIVER-INTERFACE", "CLIENT-SERVER-INTERFACE"):
            continue
        iface_name = _child_text(elem, "SHORT-NAME")
        if not iface_name:
            continue
        for child in elem:
            if _local_tag(child) == "VARIABLE-DATA-PROTOTYPE" and _child_text(child, "SHORT-NAME") == name:
                defining_interfaces.append(iface_name)
                break
    # 2) SWCs that use these interfaces (ports pointing to these interfaces)
    dependents: List[str] = list(defining_interfaces)
    for iface in defining_interfaces:
        swcs = list_swcs_using_interface(root, iface)
        for s in swcs:
            if s not in dependents:
                dependents.append(s)
    return dependents
