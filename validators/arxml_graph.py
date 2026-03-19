"""
Build a simple AUTOSAR architecture graph (SWC -> Port -> Interface -> SWC).

This is deterministic and does not depend on any external graph libraries.
The Streamlit UI can render the returned structure as a readable graph-like view.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


def _local_tag(elem: ET.Element) -> str:
    """Return local tag name without namespace."""
    if elem is None or not elem.tag:
        return ""
    return elem.tag.split("}", 1)[1] if "}" in elem.tag else elem.tag


def _child_text(elem: Optional[ET.Element], local_name: str, default: str = "") -> str:
    """Get text of first child with given local tag name (any namespace)."""
    if elem is None:
        return default
    for child in elem:
        if _local_tag(child) == local_name and child.text:
            return child.text.strip()
    return default


def _extract_port_short_name_from_ref(elem: Optional[ET.Element]) -> Optional[str]:
    """
    From a PROVIDER-IREF or REQUESTER-IREF element, extract the port prototype short name
    (last segment of ref). Mirrors logic used in compare_arxml for connector maps.
    """
    if elem is None:
        return None
    text = (elem.text or "").strip()
    if not text:
        for child in elem:
            if _local_tag(child) in (
                "TARGET-P-PORT-REF",
                "TARGET-R-PORT-REF",
                "TARGET-P-PORT-PROTOTYPE-REF",
                "TARGET-R-PORT-PROTOTYPE-REF",
            ):
                text = (child.text or "").strip()
                break
            t = (child.text or "").strip()
            if t:
                text = t
                break
    if not text:
        return None
    segment = text.split("/")[-1].strip() if "/" in text else text
    return segment or None


@dataclass
class PortNode:
    name: str
    port_type: str  # "P-PORT" or "R-PORT"
    interface: str  # interface short name (last path segment) if available


@dataclass
class SwcNode:
    name: str
    ports: List[PortNode]


@dataclass
class InterfaceNode:
    name: str
    kind: str  # e.g. "SENDER-RECEIVER-INTERFACE" or "CLIENT-SERVER-INTERFACE"


@dataclass
class GraphEdge:
    source: str
    target: str
    kind: str  # "swc-port", "port-interface", "swc-swc"
    interface_name: str = ""  # for swc-swc: interface short name carrying the connection


@dataclass
class ArxmlGraph:
    components: Dict[str, SwcNode]
    interfaces: Dict[str, InterfaceNode]
    edges: List[GraphEdge]


def _build_component_graph(root: ET.Element) -> ArxmlGraph:
    """
    Build an in-memory graph representation:
      - components: SWC/ComponentPrototype short names and their ports
      - interfaces: interface short names
      - edges: swc-port, port-interface, swc-swc (via ASSEMBLY-SW-CONNECTOR)
    Uses a single depth-first pass to track current SWC by path.
    """
    components: Dict[str, SwcNode] = {}
    interfaces: Dict[str, InterfaceNode] = {}
    edges: List[GraphEdge] = []
    # Stack of (tag, short_name) for path; we use the topmost SWC-type as owner for ports.
    path_stack: List[Tuple[str, str]] = []
    current_swc: Optional[str] = None

    def visit(elem: ET.Element) -> None:
        nonlocal current_swc
        tag = _local_tag(elem)
        short_name = _child_text(elem, "SHORT-NAME")
        if tag in ("APPLICATION-SOFTWARE-COMPONENT-TYPE", "COMPONENT-PROTOTYPE", "COMPOSITION-SW-COMPONENT-TYPE") and short_name:
            path_stack.append((tag, short_name))
            current_swc = short_name
            if current_swc and current_swc not in components:
                components[current_swc] = SwcNode(name=current_swc, ports=[])
        if tag in ("SENDER-RECEIVER-INTERFACE", "CLIENT-SERVER-INTERFACE") and short_name and short_name not in interfaces:
            interfaces[short_name] = InterfaceNode(name=short_name, kind=tag)
        if tag in ("P-PORT-PROTOTYPE", "R-PORT-PROTOTYPE"):
            port_name = short_name or ""
            if port_name:
                port_type = "P-PORT" if tag == "P-PORT-PROTOTYPE" else "R-PORT"
                ref = ""
                for child in elem:
                    ctag = _local_tag(child)
                    if ctag in ("PROVIDED-INTERFACE-TREF", "REQUIRED-INTERFACE-TREF"):
                        ref = (child.text or "").strip()
                        break
                iface_short = ref.strip("/").split("/")[-1] if ref else ""
                owner_key = current_swc or "external_component"
                if owner_key not in components:
                    components[owner_key] = SwcNode(name=owner_key, ports=[])
                port_node = PortNode(name=port_name, port_type=port_type, interface=iface_short)
                components[owner_key].ports.append(port_node)
                edges.append(GraphEdge(source=owner_key, target=port_name, kind="swc-port"))
                if iface_short:
                    edges.append(GraphEdge(source=port_name, target=iface_short, kind="port-interface"))
        for child in elem:
            visit(child)
        if tag in ("APPLICATION-SOFTWARE-COMPONENT-TYPE", "COMPONENT-PROTOTYPE", "COMPOSITION-SW-COMPONENT-TYPE") and short_name:
            path_stack.pop()
            current_swc = path_stack[-1][1] if path_stack else None

    visit(root)

    # port short name -> interface short name (from any component's port with that name)
    port_to_interface: Dict[str, str] = {}
    for swc in components.values():
        for p in swc.ports:
            if p.interface and p.name not in port_to_interface:
                port_to_interface[p.name] = p.interface

    # Assembly connectors: component-to-component edges with interface name
    for elem in root.iter():
        if _local_tag(elem) != "ASSEMBLY-SW-CONNECTOR":
            continue
        provider_name = None
        requester_name = None
        for child in elem:
            tag = _local_tag(child)
            if tag == "PROVIDER-IREF":
                provider_name = _extract_port_short_name_from_ref(child)
            elif tag == "REQUESTER-IREF":
                requester_name = _extract_port_short_name_from_ref(child)
        if not provider_name and not requester_name:
            continue
        if provider_name and requester_name:
            iface = port_to_interface.get(provider_name) or port_to_interface.get(requester_name) or ""
            edges.append(GraphEdge(source=provider_name, target=requester_name, kind="swc-swc", interface_name=iface))

    return ArxmlGraph(components=components, interfaces=interfaces, edges=edges)


def build_arxml_graph(file_path: str) -> Tuple[Optional[ArxmlGraph], Optional[str]]:
    """
    Entry point for UI and CLI.
    Returns (graph, error_message). On error, graph is None and error_message is non-empty.
    """
    if not os.path.isfile(file_path):
        return None, f"File not found: {file_path}"
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        return None, f"Invalid ARXML: {e}"
    except Exception as e:
        return None, str(e)
    return _build_component_graph(root), None

