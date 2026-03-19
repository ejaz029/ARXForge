"""
Render ARXML architecture graph with PyVis for interactive visualization.
Adapter from ArxmlGraph + conn_data to PyVis Network; returns HTML for embedding in Streamlit.
"""
from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, Tuple

# ArxmlGraph is from validators; we accept it as Any to avoid circular imports, or type as needed
try:
    from pyvis.network import Network
except ImportError:
    Network = None  # type: ignore[misc, assignment]


# Node color for SWC (professional blue)
SWC_NODE_COLOR = "#4A90D9"
# Edge color (neutral gray)
EDGE_COLOR = "#6B7280"
# Background
BG_COLOR = "#FAFAFA"


def _filter_conn_data(
    conn_data: Dict[Tuple[str, str], Dict[str, Any]],
    search_term: str,
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Filter conn_data by search_term: keep only edges where src or tgt matches (case-insensitive)."""
    if not search_term or not search_term.strip():
        return dict(conn_data)
    q = search_term.strip().lower()
    return {
        (src, tgt): data
        for (src, tgt), data in conn_data.items()
        if q in src.lower() or q in tgt.lower()
    }


def render_arxml_graph_pyvis(
    arxml_graph: Any,
    conn_data: Dict[Tuple[str, str], Dict[str, Any]],
    search_term: str = "",
    height: str = "600px",
    width: str = "100%",
) -> str:
    """
    Build an interactive PyVis network from ArxmlGraph and conn_data, return HTML string.

    Args:
        arxml_graph: ArxmlGraph (components, interfaces, edges) from validators.arxml_graph.
        conn_data: (src_swc, dst_swc) -> {"count": N, "interfaces": [names]}.
        search_term: If set, only include nodes/edges matching this term.
        height: CSS height for the iframe.
        width: CSS width for the iframe.

    Returns:
        HTML string to pass to st.components.v1.html(). If pyvis is not installed, returns
        a short HTML message asking to install pyvis.
    """
    if Network is None:
        return (
            "<!DOCTYPE html><html><body style='font-family:sans-serif;padding:1.5rem;max-width:480px;'>"
            "<p><strong>Interactive graph requires <code>pyvis</code>.</strong></p>"
            "<p>Install it in the <em>same environment</em> you use to run Streamlit (e.g. activate your venv first):</p>"
            "<pre style='background:#eee;padding:0.5rem;border-radius:4px;'>pip install pyvis</pre>"
            "<p>Then restart the Streamlit app and choose &quot;Interactive (PyVis)&quot; again.</p>"
            "</body></html>"
        )

    filtered = _filter_conn_data(conn_data, search_term)
    if not filtered:
        return (
            "<!DOCTYPE html><html><body style='font-family:sans-serif;padding:1rem;'>"
            "<p>No connections to display.</p></body></html>"
        )

    net = Network(
        height=height,
        width=width,
        directed=True,
        bgcolor=BG_COLOR,
    )

    # Collect all node IDs from filtered edges
    node_ids = set()
    for (src, tgt) in filtered:
        node_ids.add(src)
        node_ids.add(tgt)

    # Add nodes: one per SWC, with tooltip (title) = port count
    components = getattr(arxml_graph, "components", {}) or {}
    for nid in sorted(node_ids):
        swc = components.get(nid)
        port_count = len(swc.ports) if swc else 0
        title = f"{nid}\nPorts: {port_count}"
        net.add_node(
            nid,
            label=nid,
            title=title,
            color=SWC_NODE_COLOR,
            shape="box",
        )

    # Add edges with interface names as label and full list in title
    for (src, tgt), data in filtered.items():
        interfaces = data.get("interfaces", []) or []
        count = data.get("count", 0)
        label = ", ".join(interfaces[:5]) if interfaces else (str(count) if count > 1 else "")
        if interfaces and len(interfaces) > 5:
            label += "..."
        title = "Interfaces: " + ", ".join(interfaces) if interfaces else f"Connectors: {count}"
        net.add_edge(src, tgt, label=label or None, title=title, color=EDGE_COLOR)

    # Physics and options for readability
    net.set_options("""
    var options = {
      "nodes": {
        "font": { "size": 14, "face": "Arial" },
        "borderWidth": 1,
        "borderWidthSelected": 2
      },
      "edges": {
        "font": { "size": 11, "face": "Arial", "align": "middle" },
        "arrows": { "to": { "enabled": true } },
        "smooth": { "type": "cubicBezier" }
      },
      "physics": {
        "enabled": true,
        "solver": "forceAtlas2Based",
        "forceAtlas2Based": {
          "gravitationalConstant": -50,
          "centralGravity": 0.01,
          "springLength": 150,
          "springConstant": 0.08
        },
        "stabilization": { "iterations": 150 }
      }
    }
    """)

    # PyVis: save to temp file then read (works on Streamlit Cloud /tmp)
    fd, path = tempfile.mkstemp(suffix=".html", prefix="pyvis_arxml_")
    try:
        os.close(fd)
        net.save_graph(path)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
