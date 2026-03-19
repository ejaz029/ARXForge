# import streamlit as st
# import os
# import sys

# # ✅ Set page config first
# st.set_page_config(page_title="AUTOSAR ARXML Validator & Chatbot", layout="wide")

# # ✅ Add root directory to sys.path
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# # ✅ Imports
# from ai.ai_chatbot import chatbot_interface
# from app.file_utils import load_arxml_file
# from validators.schema_validation import validate_arxml_schema
# from validators.data_consistency import validate_data

# # ✅ Ensure uploads folder exists
# UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "uploads")
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# def main():
#     st.title(" AUTOSAR ARXML Validator & AI Chatbot")

#     menu = ["Chatbot", "ARXML Validator", "Upload & View ARXML"]
#     choice = st.sidebar.selectbox("🔍 Select Feature", menu)

#     if choice == "Chatbot":
#         # ✅ Pass folder path (string) to chatbot
#         chatbot_interface(upload_dir=UPLOAD_FOLDER)

#     elif choice == "ARXML Validator":
#         st.subheader("🛠️ ARXML File Validation")
#         uploaded_file = st.file_uploader("📤 Upload ARXML File for Validation", type=["arxml"])
#         if uploaded_file:
#             file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.name)
#             with open(file_path, "wb") as f:
#                 f.write(uploaded_file.getbuffer())
#             st.success(f"✅ File uploaded successfully: {uploaded_file.name}")
            
#             # Create path to your existing XSD schema file
#             xsd_schema_path = os.path.join(os.path.dirname(__file__), "..", "AUTOSAR_schema.xsd")

# # Call function with both parameters and capture both return values
#             is_valid, validation_errors = validate_arxml_schema(file_path, xsd_schema_path)

# # Update your conditional check
#             if not is_valid:
#                 st.error("❌ Validation Errors Found!")
#                 for err in validation_errors:
#                     st.write(f"🔴 {err}")
#             else:
#                 st.success("✅ ARXML file is valid!")
#             # validation_errors = validate_arxml_schema(file_path)
#             # if validation_errors:
#             #     st.error("❌ Validation Errors Found!")
#             #     for err in validation_errors:
#             #         st.write(f"🔴 {err}")
#             # else:
#             #     st.success("✅ ARXML file is valid!")
            
#     elif choice == "Upload & View ARXML":
#         st.subheader("📄 Upload & View ARXML File")
#         uploaded_file = st.file_uploader("📤 Upload ARXML File", type=["arxml"])
#         if uploaded_file:
#             file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.name)
#             with open(file_path, "wb") as f:
#                 f.write(uploaded_file.getbuffer())
#             st.success(f"✅ File uploaded successfully: {uploaded_file.name}")
#             arxml_content = load_arxml_file(file_path)
#             st.text_area("📑 ARXML Content Preview", arxml_content, height=300)

# if __name__ == "__main__":
#     main()

import os
import sys
import warnings
import xml.etree.ElementTree as ET
import xml.dom.minidom

# Load environment variables FIRST before any other imports
from dotenv import load_dotenv
load_dotenv()  # Load .env file

# Suppress all warnings before importing streamlit
warnings.filterwarnings("ignore")
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow INFO, WARNING, and ERROR messages

# Suppress TensorFlow and Hugging Face / embedding model noise before any imports
import logging
logging.getLogger('tensorflow').setLevel(logging.ERROR)
logging.getLogger('tf_keras').setLevel(logging.ERROR)
logging.getLogger('transformers').setLevel(logging.ERROR)
logging.getLogger('sentence_transformers').setLevel(logging.WARNING)

import streamlit as st

# Suppress noisy WebSocketClosedError / StreamClosedError task traces from Tornado
try:
    import asyncio

    def _streamlit_ws_exception_handler(loop, ctx):
        exc = ctx.get("exception")
        if exc is not None:
            cname = type(exc).__name__
            if cname in ("WebSocketClosedError", "StreamClosedError", "ConnectionResetError"):
                return
        if getattr(loop, "_default_exception_handler", None) is not None:
            loop._default_exception_handler(loop, ctx)

    _loop = asyncio.get_event_loop()
    if _loop is not None:
        _loop.set_exception_handler(_streamlit_ws_exception_handler)
except Exception:
    pass

# Additional warning suppression
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*torch.classes.*")
warnings.filterwarnings("ignore", message=".*RuntimeError.*no running event loop.*")
warnings.filterwarnings("ignore", message=".*HuggingFaceEmbeddings.*deprecated.*")
warnings.filterwarnings("ignore", message=".*Chain.run.*deprecated.*")
warnings.filterwarnings("ignore", message=".*tf.losses.*deprecated.*")
warnings.filterwarnings("ignore", message=".*tf.reset_default_graph.*deprecated.*")
warnings.filterwarnings("ignore", message=".*sparse_softmax_cross_entropy.*deprecated.*")
warnings.filterwarnings("ignore", message=".*oneDNN.*")
warnings.filterwarnings("ignore", message=".*unauthenticated.*HF.*")
warnings.filterwarnings("ignore", message=".*HF_TOKEN.*")

# Suppress TensorFlow warnings after import
try:
    import tensorflow as tf
    tf.get_logger().setLevel('ERROR')
    # Disable TensorFlow deprecation warnings
    tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)
except ImportError:
    pass

# ✅ Set page config
st.set_page_config(page_title="ARXForge — AUTOSAR ARXML Validator & AI Agent", layout="wide")

# ✅ Fix import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ✅ Imports
from ai import ai_chatbot as _ai_chatbot
from ai.ai_chatbot import chatbot_interface, AGENT_LAST_RUN_KEY, AGENT_CHAT_HISTORY_KEY
inject_theme = getattr(_ai_chatbot, "inject_theme", lambda: None)
from app.file_utils import load_arxml_folder, is_arxml_only, safe_upload_filename, MAX_UPLOAD_BYTES
from validators.schema_validation import validate_arxml_schema
from validators.data_consistency import validate_data
from validators.compare_arxml import compare_two_arxml_files
from validators.audit_runner import run_audit_validators
from validators.arxml_graph import build_arxml_graph
from ai.compare_report import summarize_comparison_with_llm
from app.graph_visualization import render_arxml_graph_pyvis
import streamlit.components.v1 as components

# ✅ Uploads folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def pretty_print_xml(root):
    """Returns pretty-printed XML string from ElementTree root."""
    xml_str = ET.tostring(root, encoding="utf-8")
    return xml.dom.minidom.parseString(xml_str).toprettyxml()


def compare_arxml_interface(upload_dir):
    """Compare two ARXML files: file selection, validation, Compare button, results panel."""
    st.subheader("Compare two ARXML files")
    os.makedirs(upload_dir, exist_ok=True)

    try:
        arxml_files = sorted(f for f in os.listdir(upload_dir) if is_arxml_only(f))
    except FileNotFoundError:
        st.error("Upload directory not found.")
        return
    if not arxml_files:
        st.info("No ARXML files found. Upload .arxml files in AI Agent or Upload & View ARXML first.")
        return
    if len(arxml_files) < 2:
        st.info("Upload at least two .arxml files to compare.")
        return

    col_a, col_b = st.columns(2)
    with col_a:
        file_a = st.selectbox("File A", arxml_files, key="compare_file_a")
    with col_b:
        st.markdown(
            '<div id="compare-file-b-fossil" style="background-color:#787276;color:#f0f0f0;border-radius:6px;padding:6px 10px;margin-bottom:8px;font-weight:500;">File B</div>',
            unsafe_allow_html=True,
        )
        file_b_list = [f for f in arxml_files if f != file_a]
        file_b = st.selectbox("File B", file_b_list, key="compare_file_b", label_visibility="collapsed") if file_b_list else None
    if file_a and file_b and file_a == file_b:
        st.warning("Select two different files.")
        file_b = None

    COMPARE_LAST_RESULT_KEY = "_compare_last_result"
    COMPARE_LAST_FILES_KEY = "_compare_last_files"

    run_compare = st.button("Compare")
    if run_compare and file_a and file_b:
        path_a = os.path.join(upload_dir, file_a)
        path_b = os.path.join(upload_dir, file_b)
        with st.spinner("Comparing..."):
            try:
                out = compare_two_arxml_files(path_a, path_b)
            except Exception as e:
                st.error(f"Comparison failed: {e}")
                return
        if out.get("error"):
            st.error(out["error"])
            return
        st.session_state[COMPARE_LAST_RESULT_KEY] = out
        st.session_state[COMPARE_LAST_FILES_KEY] = (file_a, file_b)
        st.success("Comparison complete.")
    out = st.session_state.get(COMPARE_LAST_RESULT_KEY)
    file_pair = st.session_state.get(COMPARE_LAST_FILES_KEY)
    # Only show results when the current selection matches the compared files (avoid wrong file names in header)
    selection_matches = bool(
        file_pair and file_a and file_b and len(file_pair) == 2 and (file_a, file_b) == tuple(file_pair)
    )
    if out and not out.get("error") and file_pair and selection_matches:
        file_a_display, file_b_display = file_pair
        with st.expander("Results", expanded=True):
            st.markdown(out.get("summary", ""))
            st.markdown("---")
            st.markdown("**Counts**")
            counts_a = out.get("counts_a", {}) or {}
            counts_b = out.get("counts_b", {}) or {}
            total_a = sum(counts_a.values())
            total_b = sum(counts_b.values())
            port_d = out.get("port_diff", {})
            swc_d = out.get("swc_diff", {})
            uuid_d = out.get("uuid_diff", {})
            def _diff_badge(label: str, a: int, b: int) -> str:
                diff = b - a
                if diff > 0:
                    color = "#1976d2"  # blue for increase
                elif diff < 0:
                    color = "#d32f2f"  # red for decrease
                else:
                    color = "#388e3c"  # green for no change
                sign = f"{diff:+d}"
                return (
                    "<span style='display:inline-block;border-radius:12px;"
                    "padding:2px 8px;margin:0 4px 4px 0;background-color:rgba(0,0,0,0.05);"
                    f"color:{color};font-size:0.85rem;'><strong>{label}</strong>: "
                    f"{a} \u2192 {b} ({sign})</span>"
                )

            # For ports, if the entire increase is due to renames, treat net change as 0 for the badge.
            ports_a_raw = port_d.get("count_a", 0)
            ports_b_raw = port_d.get("count_b", 0)
            ports_renamed = port_d.get("renamed_count", 0)
            ports_delta_raw = ports_b_raw - ports_a_raw
            if ports_renamed and ports_delta_raw == ports_renamed:
                ports_b_effective = ports_a_raw
            else:
                ports_b_effective = ports_b_raw

            badges_html = "".join(
                [
                    _diff_badge("Elements", total_a, total_b),
                    _diff_badge("Ports", ports_a_raw, ports_b_effective),
                    _diff_badge("SWCs", swc_d.get("count_a", 0), swc_d.get("count_b", 0)),
                    _diff_badge("UUIDs", uuid_d.get("count_a", 0), uuid_d.get("count_b", 0)),
                ]
            )
            st.markdown(badges_html, unsafe_allow_html=True)

            # Compact change summary header (include renamed; optional per-category summary)
            h = out.get("hierarchy_diff") or {}
            added_ct = len(h.get("added") or [])
            removed_ct = len(h.get("removed") or [])
            modified_ct = len(h.get("modified") or [])
            renamed_ct = len(h.get("renamed") or [])
            ports_delta = port_d.get("count_b", 0) - port_d.get("count_a", 0)
            st.markdown(
                f"Changes: **{added_ct} added**, **{removed_ct} removed**, **{modified_ct} modified**, **{renamed_ct} renamed** "
                f"(Ports: {ports_delta:+d})"
            )
            sc = out.get("summary_counts") or {}
            if sc:
                parts = [f"Total: {sc.get('total', 0)}"]
                for k in ("architecture", "interfaces", "data_model", "signals", "metadata"):
                    if sc.get(k):
                        parts.append(f"{k.replace('_', ' ').title()}: {sc[k]}")
                if len(parts) > 1:
                    st.caption("By category: " + ", ".join(parts))
            only_a = out.get("only_in_a", [])
            only_b = out.get("only_in_b", [])
            if only_a or only_b:
                st.markdown("**Tag differences**")
                if only_a:
                    st.caption("Tags only in File A (sample): " + ", ".join(only_a[:15]))
                if only_b:
                    st.caption("Tags only in File B (sample): " + ", ".join(only_b[:15]))
            pa = port_d.get("only_in_a", [])
            pb = port_d.get("only_in_b", [])
            if pa or pb:
                st.markdown("**Ports**")
                if pa:
                    st.caption("Only in A: " + ", ".join(pa[:20]) + ("..." if len(pa) > 20 else ""))
                if pb:
                    st.caption("Only in B: " + ", ".join(pb[:20]) + ("..." if len(pb) > 20 else ""))
            sa = swc_d.get("only_in_a", [])
            sb = swc_d.get("only_in_b", [])
            if sa or sb:
                st.markdown("**SWCs**")
                if sa:
                    st.caption("Only in A: " + ", ".join(sa[:20]) + ("..." if len(sa) > 20 else ""))
                if sb:
                    st.caption("Only in B: " + ", ".join(sb[:20]) + ("..." if len(sb) > 20 else ""))
            # Hierarchy diff: prefer grouped view to reduce path noise
            h = out.get("hierarchy_diff") or {}
            hg = out.get("hierarchy_diff_grouped") or {}
            if h:
                st.markdown("---")
                st.markdown("**Hierarchy diff**")
                added_grouped = hg.get("added") or []
                if added_grouped:
                    st.markdown("🟢 **Added (in File B)**")
                    for g in added_grouped:
                        short_names = ", ".join(g.get("short_names", []))
                        st.caption(
                            f"`{g.get('parent', '')}`  [{g.get('type', '')}] added: {short_names}"
                        )
                removed_grouped = hg.get("removed") or []
                if removed_grouped:
                    st.markdown("🔴 **Removed (from File A)**")
                    for g in removed_grouped:
                        short_names = ", ".join(g.get("short_names", []))
                        st.caption(
                            f"`{g.get('parent', '')}`  [{g.get('type', '')}] removed: {short_names}"
                        )
                modified_grouped = hg.get("modified") or []
                if modified_grouped:
                    st.markdown("🟡 **Modified**")
                    for g in modified_grouped:
                        items = g.get("items", [])
                        summaries = ", ".join(
                            f"{it.get('short_name', '')} ({it.get('summary', '')})" for it in items
                        )
                        st.caption(
                            f"`{g.get('parent', '')}`  [{g.get('type', '')}] modified: {summaries}"
                        )
                renamed_grouped = hg.get("renamed") or []
                if renamed_grouped:
                    st.markdown("🔵 **Renamed**")
                    for g in renamed_grouped:
                        pairs = g.get("pairs", [])
                        renames = ", ".join(
                            f"{p.get('from', '')} → {p.get('to', '')}" for p in pairs
                        )
                        st.caption(
                            f"`{g.get('parent_b', '')}`  [{g.get('type', '')}] renamed: {renames}"
                        )

            # Impact Analysis: affected SWCs, signals, interfaces, RTE connections per changed port/interface
            impact_list = out.get("dependency_impact") or []
            if impact_list:
                st.markdown("---")
                impact_to_show = impact_list[:20]
                with st.expander("**Impact Analysis**", expanded=len(impact_to_show) <= 5):
                    for di in impact_to_show:
                        element = di.get("element", "")
                        change = di.get("change", "")
                        st.markdown(f"**Port/Interface {element}** ({change})")
                        swc_names = di.get("affected_swc_names") or []
                        if swc_names:
                            st.markdown("**Affected SWCs**")
                            for name in swc_names:
                                st.markdown(f"- {name}")
                        else:
                            comps = di.get("affected_components") or []
                            segments = [p.strip("/").split("/")[-1] for p in comps if p]
                            seen = set()
                            if segments:
                                st.markdown("**Affected SWCs**")
                                for seg in segments:
                                    if seg and seg not in seen:
                                        seen.add(seg)
                                        st.markdown(f"- {seg}")
                        affected_signals = di.get("affected_signals") or []
                        if affected_signals:
                            st.markdown("**Affected signals**")
                            for sig in affected_signals[:15]:
                                st.markdown(f"- {sig}")
                            if len(affected_signals) > 15:
                                st.caption(f"... and {len(affected_signals) - 15} more")
                        affected_interfaces = di.get("affected_interfaces") or []
                        if affected_interfaces:
                            st.markdown("**Affected interfaces**")
                            for iface in affected_interfaces:
                                st.markdown(f"- {iface}")
                        conn_summary = di.get("connector_summary", "")
                        if conn_summary:
                            st.markdown(f"**Affected connectors:** {conn_summary}")
                        rte = di.get("rte_mappings") or {}
                        file_a_count = rte.get("file_a", 0)
                        file_b_count = rte.get("file_b", 0)
                        if file_a_count or file_b_count:
                            st.markdown(
                                f"**Affected RTE connections:** File A: {file_a_count} mapping(s), File B: {file_b_count} mapping(s)"
                            )
                        else:
                            st.markdown("**Affected RTE connections:** N/A")
                        severity = di.get("impact_severity", "")
                        if severity:
                            st.markdown(f"Impact severity: **{severity}**")
                        score = di.get("impact_score")
                        if score is not None:
                            st.markdown(f"Impact score: **{score} / 10**")
                        st.markdown("")

        st.markdown("---")
        st.caption(
            "Report structure: **COMPARISON SUMMARY** (Architecture / Interface / Data model) | "
            "**ENGINEERING ANALYSIS** (Impact summary / Risk analysis / Testing recommendations)."
        )
        if st.button("Generate engineering report (LLM)", key="compare_llm_report_btn"):
            with st.spinner("Generating engineering report..."):
                report = summarize_comparison_with_llm(out, file_a_display, file_b_display)
            if report.startswith("Engineering report unavailable") or report.startswith("Could not"):
                st.warning(report)
            else:
                with st.expander("Engineering report", expanded=True):
                    st.markdown(report)
    elif file_a and file_b and not selection_matches:
        st.info("Click **Compare** to compare the selected files (File A vs File B).")


def architecture_graph_interface(upload_dir):
    """Architecture Graph: select ARXML, show SWC -> Port -> Interface graph."""
    st.subheader("Architecture Graph")
    os.makedirs(upload_dir, exist_ok=True)
    try:
        arxml_files = sorted(f for f in os.listdir(upload_dir) if is_arxml_only(f))
    except FileNotFoundError:
        st.error("Upload directory not found.")
        return
    if not arxml_files:
        st.info("Upload ARXML files in AI Agent or Upload & View first.")
        return
    st.markdown("Configure view")
    col_opts1, col_opts2 = st.columns(2)
    with col_opts1:
        show_components = st.checkbox("Show components", value=True, key="graph_show_components")
        show_connections = st.checkbox("Show connections", value=True, key="graph_show_connections")
    with col_opts2:
        show_interfaces = st.checkbox("Show interfaces", value=True, key="graph_show_interfaces")
        show_visual = st.checkbox("Show visual graph", value=False, key="graph_show_visual")
    search_term = st.text_input("Search component (optional)", value="", key="graph_search")

    graph_file = st.selectbox("Select ARXML file", arxml_files, key="graph_file")
    if not graph_file:
        return
    path = os.path.join(upload_dir, graph_file)
    if st.button("Build graph", key="build_graph_btn"):
        with st.spinner("Building graph..."):
            graph, err = build_arxml_graph(path)
        if err:
            st.error(err)
            return
        st.session_state["_arxml_graph"] = graph
        st.session_state["_arxml_graph_file"] = graph_file
    g = st.session_state.get("_arxml_graph")
    if g and st.session_state.get("_arxml_graph_file") == graph_file:
        # Build helper indices
        port_to_swc: dict[str, str] = {}
        for swc in g.components.values():
            for p in swc.ports:
                port_to_swc[p.name] = swc.name
        # (src_swc, dst_swc) -> {"count": N, "interfaces": [names]}
        conn_data: dict[tuple[str, str], dict] = {}
        for e in g.edges:
            if e.kind != "swc-swc":
                continue
            src = port_to_swc.get(e.source, e.source)
            tgt = port_to_swc.get(e.target, e.target)
            key = (src, tgt)
            if key not in conn_data:
                conn_data[key] = {"count": 0, "interfaces": []}
            conn_data[key]["count"] += 1
            if getattr(e, "interface_name", "") and e.interface_name not in conn_data[key]["interfaces"]:
                conn_data[key]["interfaces"].append(e.interface_name)
        # Interface usage counts
        iface_users: dict[str, set[str]] = {}
        for swc in g.components.values():
            for p in swc.ports:
                if p.interface:
                    iface_users.setdefault(p.interface, set()).add(swc.name)
        # Summary bar
        st.markdown(
            f"Components: **{len(g.components)}**  |  "
            f"Interfaces: **{len(g.interfaces)}**  |  "
            f"Connections: **{len(conn_data)}**"
        )
        # Component detail view: select one SWC to see ports, interfaces, connections
        detail_candidates = [n for n in g.components if n != "external_component" or g.components[n].ports]
        if detail_candidates:
            selected_swc = st.selectbox(
                "Component details",
                options=[""] + detail_candidates,
                format_func=lambda x: "(select component)" if x == "" else x,
                key="graph_detail_swc",
            )
            if selected_swc:
                swc = g.components[selected_swc]
                with st.expander("Component Details", expanded=True):
                    st.markdown(f"**Ports** ({len(swc.ports)})")
                    by_iface_detail: dict[str, list] = {}
                    for p in swc.ports:
                        by_iface_detail.setdefault(p.interface or "(no interface)", []).append(p)
                    for iface_name, ports in by_iface_detail.items():
                        st.caption(f"Interface: {iface_name}")
                        for p in ports:
                            st.caption(f"  {p.port_type} {p.name}")
                    iface_list = sorted({p.interface for p in swc.ports if p.interface})
                    st.markdown(f"**Interfaces used** ({len(iface_list)})")
                    for ifn in iface_list:
                        st.caption(f"  {ifn}")
                    outgoing = [(tgt, data) for (src, tgt), data in conn_data.items() if src == selected_swc]
                    incoming = [(src, data) for (src, tgt), data in conn_data.items() if tgt == selected_swc]
                    st.markdown("**Connections**")
                    if outgoing:
                        st.caption("Outgoing:")
                        for tgt, data in outgoing:
                            ifaces = data.get("interfaces", []) or []
                            lbl = ", ".join(ifaces[:8]) if ifaces else str(data.get("count", 0))
                            if len(ifaces) > 8:
                                lbl += f" (+{len(ifaces) - 8} more)"
                            st.caption(f"  → {tgt} ({lbl})")
                    if incoming:
                        st.caption("Incoming:")
                        for src, data in incoming:
                            ifaces = data.get("interfaces", []) or []
                            lbl = ", ".join(ifaces[:8]) if ifaces else str(data.get("count", 0))
                            if len(ifaces) > 8:
                                lbl += f" (+{len(ifaces) - 8} more)"
                            st.caption(f"  ← {src} ({lbl})")
                    if not outgoing and not incoming:
                        st.caption("  No SWC–SWC connections.")
        # Components section (hide external_component when it has no ports)
        if show_components:
            st.markdown("**Components**")
            for name, swc in g.components.items():
                if name == "external_component" and not swc.ports:
                    continue
                if search_term and search_term.lower() not in name.lower():
                    continue
                with st.expander(f"SWC: {name}", expanded=len(g.components) <= 5):
                    by_iface: dict[str, list] = {}
                    for p in swc.ports:
                        by_iface.setdefault(p.interface or "(no interface)", []).append(p)
                    for iface_name, ports in by_iface.items():
                        st.caption(f"Interface: {iface_name}")
                        for p in ports:
                            st.caption(f"  {p.port_type} {p.name}")
        # Interfaces section
        if show_interfaces:
            st.markdown("**Interfaces**")
            for name, iface in list(g.interfaces.items())[:50]:
                prefix = "SR" if iface.kind == "SENDER-RECEIVER-INTERFACE" else (
                    "CS" if iface.kind == "CLIENT-SERVER-INTERFACE" else iface.kind
                )
                users = iface_users.get(name, set())
                used_by = f" (used by {len(users)} SWC(s))" if users else ""
                st.caption(f"  {prefix}: {name}{used_by}")
            if len(g.interfaces) > 50:
                st.caption(f"  ... and {len(g.interfaces) - 50} more")
        # Connections section (with interface names per pair)
        if show_connections and conn_data:
            st.markdown("**Connections**")
            for (src, tgt), data in list(conn_data.items())[:50]:
                if search_term and not (
                    search_term.lower() in src.lower() or search_term.lower() in tgt.lower()
                ):
                    continue
                count = data.get("count", 0)
                interfaces = data.get("interfaces", []) or []
                count_str = f" ({count})" if count != 1 else ""
                st.caption(f"  **{src} → {tgt}**{count_str}")
                if interfaces:
                    for iface in interfaces[:15]:
                        st.caption(f"    — {iface}")
                    if len(interfaces) > 15:
                        st.caption(f"    — ... and {len(interfaces) - 15} more")
        # Visual graph: view selector (Simple Graphviz | Interactive PyVis), then render
        if show_visual and conn_data:
            # Filter by search term for both views
            if search_term and search_term.strip():
                q = search_term.strip().lower()
                filtered_conn_data = {
                    (src, tgt): data
                    for (src, tgt), data in conn_data.items()
                    if q in src.lower() or q in tgt.lower()
                }
            else:
                filtered_conn_data = conn_data

            viz_mode = st.radio(
                "Visualization",
                options=["Simple (Graphviz)", "Interactive (PyVis)"],
                index=0,
                key="graph_viz_mode",
                horizontal=True,
            )

            if viz_mode == "Interactive (PyVis)":
                try:
                    html = render_arxml_graph_pyvis(
                        g,
                        filtered_conn_data,
                        search_term=search_term or "",
                        height="600px",
                        width="100%",
                    )
                    st.caption("Rectangle = Component (SWC). Edge label = Interface(s). Hover for details.")
                    components.html(html, height=650, scrolling=False)
                except Exception as e:
                    st.warning(f"Interactive graph failed: {e}. Use Simple (Graphviz) or install: pip install pyvis")
            else:
                dot_lines = ["digraph G {", "  rankdir=LR;"]
                all_nodes = set()
                for (src, tgt) in filtered_conn_data:
                    all_nodes.add(src)
                    all_nodes.add(tgt)
                prefix_to_nodes: dict[str, set[str]] = {}
                for n in all_nodes:
                    pre = n.split("_")[0] if "_" in n else n
                    prefix_to_nodes.setdefault(pre, set()).add(n)
                for pre, nodes in prefix_to_nodes.items():
                    if len(nodes) < 2:
                        continue
                    dot_lines.append(f"  subgraph cluster_{pre} {{")
                    dot_lines.append(f'    label="{pre}";')
                    for node in sorted(nodes):
                        dot_lines.append(f'    "{node}";')
                    dot_lines.append("  }")
                for (src, tgt), data in filtered_conn_data.items():
                    interfaces = data.get("interfaces", []) or []
                    count = data.get("count", 0)
                    if interfaces:
                        label = "\\n".join(interfaces[:5]) if len(interfaces) <= 5 else "\\n".join(interfaces[:4]) + "\\n..."
                    else:
                        label = str(count) if count > 1 else ""
                    label_attr = f' [label="{label}"]' if label else ""
                    dot_lines.append(f"  \"{src}\" -> \"{tgt}\"{label_attr};")
                dot_lines.append("}")
                dot_source = "\n".join(dot_lines)
                st.graphviz_chart(dot_source)


def system_analysis_interface(upload_dir):
    """Multi-file system analysis: run audit on all ARXML files in uploads and show summary table."""
    st.subheader("System Analysis (multi-file)")
    os.makedirs(upload_dir, exist_ok=True)
    try:
        arxml_files = sorted(f for f in os.listdir(upload_dir) if is_arxml_only(f))
    except FileNotFoundError:
        st.error("Upload directory not found.")
        return
    if not arxml_files:
        st.info("Upload ARXML files in AI Agent or Upload & View first.")
        return
    xsd_path = os.path.join(os.path.dirname(__file__), "..", "AUTOSAR_schema.xsd")
    if st.button("Analyze all files", key="system_analysis_btn"):
        progress = st.progress(0)
        results_per_file = []
        for i, f in enumerate(arxml_files):
            path = os.path.join(upload_dir, f)
            rows = run_audit_validators(path, xsd_path)
            pass_count = sum(1 for r in rows if r.get("status") == "PASS")
            fail_count = sum(1 for r in rows if r.get("status") == "FAIL")
            warn_count = sum(1 for r in rows if r.get("status") == "WARNING")
            results_per_file.append({
                "file": f,
                "pass": pass_count,
                "fail": fail_count,
                "warn": warn_count,
                "rows": rows,
            })
            progress.progress((i + 1) / len(arxml_files))
        progress.empty()
        st.session_state["_system_analysis"] = results_per_file
    data = st.session_state.get("_system_analysis")
    if data:
        # Compact summary table instead of many repeated lines
        st.markdown("**Summary**")
        summary_rows = [
            {
                "File": row["file"],
                "PASS": row["pass"],
                "FAIL": row["fail"],
                "WARN": row["warn"],
            }
            for row in data
        ]
        st.table(summary_rows)
        st.markdown("---")
        st.markdown("**Per-file details (only files with issues)**")
        for row in data:
            if row["fail"] == 0 and row["warn"] == 0:
                continue
            label = f"{row['file']} (✔ {row['pass']} / ❌ {row['fail']} / ⚠ {row['warn']})"
            with st.expander(label):
                for r in row["rows"]:
                    status = r.get("status", "")
                    sym = "✔" if status == "PASS" else ("❌" if status == "FAIL" else "⚠")
                    st.caption(f"{sym} {r.get('name', '')}: {r.get('summary', '')}")


PENDING_FEATURE_KEY = "_pending_sidebar_feature"


def main():
    if PENDING_FEATURE_KEY in st.session_state:
        st.session_state["sidebar_feature"] = st.session_state.pop(PENDING_FEATURE_KEY)

    inject_theme()
    st.title("ARXForge")

    menu = [
        "AI Agent",
        "ARXML Validator",
        "Upload & View ARXML",
        "Compare ARXML",
        "Architecture Graph",
        "System Analysis",
    ]
    st.sidebar.markdown("**Features**")
    choice = st.sidebar.radio("Select feature", menu, key="sidebar_feature", label_visibility="collapsed")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Old chat**")
    history = st.session_state.get(AGENT_CHAT_HISTORY_KEY, [])
    if not history:
        st.sidebar.caption("Run a command to see history here.")
    else:
        for i, entry in enumerate(reversed(history)):
            cmd = (entry.get("command") or "")[:40]
            if len(entry.get("command") or "") > 40:
                cmd += "..."
            file_label = entry.get("file") or ""
            if file_label:
                cmd = f"{cmd} ({file_label})"
            if st.sidebar.button(cmd or f"Run {i+1}", key=f"old_chat_{i}"):
                st.session_state[AGENT_LAST_RUN_KEY] = entry.get("payload", {})
                st.session_state[PENDING_FEATURE_KEY] = "AI Agent"
                st.rerun()

    if choice == "AI Agent":
        chatbot_interface(upload_dir=UPLOAD_FOLDER)

    elif choice == "Compare ARXML":
        compare_arxml_interface(upload_dir=UPLOAD_FOLDER)

    elif choice == "Architecture Graph":
        architecture_graph_interface(upload_dir=UPLOAD_FOLDER)

    elif choice == "System Analysis":
        system_analysis_interface(upload_dir=UPLOAD_FOLDER)

    elif choice == "ARXML Validator":
        st.subheader("ARXML File Validation")
        xsd_schema_path = os.path.join(os.path.dirname(__file__), "..", "AUTOSAR_schema.xsd")

        # Validation Dashboard: select file from uploads and run all validators
        try:
            arxml_files = sorted(f for f in os.listdir(UPLOAD_FOLDER) if is_arxml_only(f))
        except FileNotFoundError:
            arxml_files = []
        if arxml_files:
            st.markdown("**Validation Dashboard**")
            dash_file = st.selectbox(
                "Select ARXML file",
                arxml_files,
                key="validator_dashboard_file",
                label_visibility="collapsed",
            )
            _dash_result_key = "_validation_dashboard_result"
            _dash_file_key = "_validation_dashboard_file"
            if st.button("Run full validation", key="validator_dashboard_btn"):
                path = os.path.join(UPLOAD_FOLDER, dash_file)
                with st.spinner("Running validators..."):
                    dashboard_results = run_audit_validators(path, xsd_schema_path)
                st.session_state[_dash_result_key] = dashboard_results
                st.session_state[_dash_file_key] = dash_file
            dashboard_results = st.session_state.get(_dash_result_key)
            dash_file_used = st.session_state.get(_dash_file_key)
            if dashboard_results and dash_file_used == dash_file:
                if dashboard_results[0].get("name") in ("File", "Parse") and dashboard_results[0].get("status") == "FAIL":
                    st.error(dashboard_results[0].get("summary", "Error"))
                else:
                    pass_count = sum(1 for r in dashboard_results if r.get("status") == "PASS")
                    fail_count = sum(1 for r in dashboard_results if r.get("status") == "FAIL")
                    warn_count = sum(1 for r in dashboard_results if r.get("status") == "WARNING")
                    st.caption(f"✔ {pass_count} passed  |  ❌ {fail_count} failed  |  ⚠ {warn_count} warning(s)")
                    cols = st.columns(3)
                    for i, r in enumerate(dashboard_results):
                        with cols[i % 3]:
                            status = r.get("status", "")
                            icon = "✔" if status == "PASS" else ("❌" if status == "FAIL" else "⚠")
                            st.markdown(f"**{icon} {r.get('name', '')}**")
                            st.caption(r.get("summary", ""))
        else:
            st.info("Upload ARXML files in AI Agent or Upload & View first to use the Validation Dashboard.")

        st.markdown("---")
        st.markdown("**Schema-only validation (upload)**")
        uploaded_file = st.file_uploader("Upload ARXML File for Validation", type=None, key="validator_upload")
        if uploaded_file:
            safe_name = safe_upload_filename(uploaded_file.name)
            if not safe_name:
                st.error("Invalid file type or filename. Only .arxml files with a safe name are accepted.")
            elif len(uploaded_file.getbuffer()) > MAX_UPLOAD_BYTES:
                st.error(f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024*1024)} MB.")
            else:
                file_path = os.path.join(UPLOAD_FOLDER, safe_name)
                try:
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.success(f"File uploaded: {safe_name}")

                    if not os.path.exists(xsd_schema_path):
                        st.error(f"XSD schema file not found at: {xsd_schema_path}")
                    else:
                        try:
                            is_valid, validation_errors = validate_arxml_schema(file_path, xsd_schema_path)

                            if not is_valid:
                                st.error("Schema Validation Failed:")
                                for err in validation_errors:
                                    st.write(err)
                            else:
                                st.success("ARXML file is valid.")
                        except Exception as e:
                            st.error(f"Error during validation: {str(e)}")
                except Exception as e:
                    st.error(f"Error saving uploaded file: {str(e)}")

    elif choice == "Upload & View ARXML":
        st.subheader("Upload ARXML File")
        uploaded_file = st.file_uploader("Upload ARXML File", type=None)
        if uploaded_file:
            safe_name = safe_upload_filename(uploaded_file.name)
            if not safe_name:
                st.error("Invalid file type or filename. Only .arxml files with a safe name are accepted.")
            elif len(uploaded_file.getbuffer()) > MAX_UPLOAD_BYTES:
                st.error(f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024*1024)} MB.")
            else:
                file_path = os.path.join(UPLOAD_FOLDER, safe_name)
                try:
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.success(f"File uploaded: {safe_name}")
                except Exception as e:
                    st.error(f"Error saving file: {str(e)}")

        st.subheader("View All ARXML Files in 'uploads/' Folder")
        try:
            arxml_data, failed_files = load_arxml_folder(UPLOAD_FOLDER)

            if not arxml_data and not failed_files:
                st.info("No ARXML files found.")
            else:
                for filename, root in arxml_data:
                    with st.expander(filename):
                        try:
                            pretty_xml = pretty_print_xml(root)
                            st.code(pretty_xml, language="xml")
                        except Exception as e:
                            st.error(f"Error formatting XML: {str(e)}")
                            st.code(ET.tostring(root, encoding="utf-8").decode(), language="xml")

                if failed_files:
                    st.error("Failed to parse some files:")
                    for filename, error_msg in failed_files:
                        st.write(f"{filename}: {error_msg}")
        except Exception as e:
            st.error(f"Error loading ARXML files: {str(e)}")

if __name__ == "__main__":
    main()
