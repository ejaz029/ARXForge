import os
import streamlit as st
from ai.rag_validation import process_query_structured
from ai.agent_tools import get_all_tools
from app.file_utils import is_arxml_only, safe_upload_filename, MAX_UPLOAD_BYTES

AGENT_LAST_RUN_KEY = "agent_last_run"
AGENT_CHAT_HISTORY_KEY = "agent_chat_history"
AGENT_CHAT_HISTORY_MAX = 30
INPUT_KEY_PREFIX = "agent_cmd_"


def inject_theme():
    """Apply grey theme (ChatGPT-like). Call from main so all pages use it."""
    _inject_theme()


def _inject_theme():
    """ChatGPT-like grey palette: soft grey background, light grey panels, no white canvas.
    Uses targeted font-family (no global *) so Streamlit icon font is not overridden.
    """
    st.markdown(
        """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
    <style>
    [data-testid="stAppViewContainer"] .stMarkdown,
    [data-testid="stAppViewContainer"] .stText,
    [data-testid="stAppViewContainer"] p,
    [data-testid="stAppViewContainer"] label,
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    .stMarkdown, .stText, .stTextInput label, .stButton button,
    [data-testid="stSelectbox"] label { font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important; }
    /* Option 3: Neutral mid-grey (enterprise) */
    [data-testid="stAppViewContainer"] { background-color: #2F3437 !important; }
    /* Brand title ARXForge accent color */
    [data-testid="stAppViewContainer"] h1 { color: #B9D9EB !important; }
    /* AI Agent subheader and Upload ARXML label – white */
    [data-testid="stAppViewContainer"] h2, [data-testid="stAppViewContainer"] h3 { color: #ffffff !important; }
    /* Left dashboard (sidebar) in darker tone */
    [data-testid="stSidebar"] { background-color: #1F2022 !important; }
    [data-testid="stSidebar"] .stMarkdown { color: #D0D4D7 !important; }
    .stMarkdown, .stText, .stTextInput label, p { color: #FFFFFF !important; }
    .stMarkdown strong { color: #FFFFFF !important; }
    [data-testid="stExpander"] label { color: #FFFFFF !important; font-family: 'Inter', sans-serif !important; }
    [data-testid="stExpander"] label > span:first-of-type { font-family: "Material Symbols Rounded", "Material Symbols", sans-serif !important; }
    /* Cards/inputs: neutral mid-grey #3A3F44 */
    .stTextInput input { background-color: #3A3F44 !important; color: #F7F7F7 !important; border: 1px solid #4A4F55 !important; }
    .stTextInput input::placeholder { color: #a0a0a0 !important; }
    .stTextInput input:focus { border-color: #22c55e !important; box-shadow: 0 0 0 1px #22c55e !important; }
    .stTextInput label { color: #D0D4D7 !important; }
    .stButton button { background-color: #22c55e !important; color: #fff !important; border: none !important; }
    .stButton button:hover { background-color: #1e9e4d !important; }
    [data-testid="stSelectbox"] { background-color: #3A3F44 !important; }
    [data-testid="stSelectbox"] > div { background-color: #3A3F44 !important; color: #F7F7F7 !important; border: 1px solid #4A4F55 !important; }
    [data-testid="stSelectbox"] label { color: #D0D4D7 !important; }
    [data-testid="stAlert"] { background-color: #3A3F44 !important; border-left: 4px solid #22c55e !important; border-color: #4A4F55 !important; }
    .agent-panel { background-color: #3A3F44; border: 1px solid #4A4F55; border-radius: 8px; padding: 12px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.06); margin-bottom: 12px; }
    div[data-testid="column"] { background-color: transparent !important; border: 1px solid #4A4F55 !important; border-radius: 8px !important; padding: 12px 16px !important; box-shadow: 0 1px 2px rgba(0,0,0,0.06) !important; }
    /* Right pane (Command + Output + Agent Activity) */
    [data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {
      background-color: #3A3F44 !important;
      border: 1px solid #4A4F55 !important;
      border-radius: 8px !important;
      padding: 12px 16px !important;
      min-height: 70vh !important;
    }
    /* Inner columns inside right pane: transparent so Fossil shows through */
    [data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child div[data-testid="column"] {
      background-color: transparent !important;
      border: none !important;
      box-shadow: none !important;
    }
    [data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child .stMarkdown,
    [data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child p,
    [data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child label {
      color: #D0D4D7 !important;
    }
    [data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child .stCaption {
      color: #D0D4D7 !important;
    }
    #compare-file-b-fossil {
      background-color: #3A3F44 !important;
      color: #F7F7F7 !important;
      border: 2px solid #4A4F55 !important;
      border-radius: 8px !important;
      padding: 6px 10px !important;
      margin-bottom: 8px !important;
      font-weight: 500 !important;
    }
    /* Upload ARXML (file uploader) – text white */
    [data-testid="stFileUploader"] {
      background-color: #3A3F44 !important;
      color: #ffffff !important;
      border: 1px solid #4A4F55 !important;
      border-radius: 8px !important;
    }
    [data-testid="stFileUploader"] section { background-color: #3A3F44 !important; color: #ffffff !important; border-color: #4A4F55 !important; }
    [data-testid="stFileUploader"] .stMarkdown, [data-testid="stFileUploader"] p, [data-testid="stFileUploader"] label, [data-testid="stFileUploader"] span { color: #ffffff !important; }
    [data-testid="stFileUploader"] button {
      background-color: #3A3F44 !important;
      color: #F7F7F7 !important;
      border: 1px solid #4A4F55 !important;
    }
    [data-testid="stFileUploader"] button:hover { background-color: #454A52 !important; }
    /* Agent Activity panel */
    #agent-activity-fossil {
      background-color: #3A3F44 !important;
      border: 1px solid #4A4F55 !important;
      border-radius: 8px !important;
      padding: 12px !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


_TOOL_LABELS = {
    "extract_ports_tool": "Ports",
    "extract_uuids_tool": "UUIDs",
    "check_duplicate_uuids_tool": "UUID duplicates",
    "validate_port_references_tool": "Port references",
    "extract_software_components": "Software components",
    "extract_ecu_instances": "ECU instances",
    "validate_schema_tool": "Schema",
    "validate_data_consistency_tool": "Data consistency",
    "validate_swc_tool": "SWC",
    "validate_communication_tool": "Communication",
    "validate_memory_tool": "Memory",
    "validate_rte_tool": "RTE",
    "validate_diagnostics_tool": "Diagnostics",
    "validate_ecu_bsw_tool": "ECU/BSW",
    "validate_version_compatibility_tool": "Version",
    "validate_component_refs_tool": "Component refs",
    "duplicate_ports_tool": "Duplicate ports",
}


def _result_display_value(tool_name, result_text, is_error):
    """Map tool result to a short display value (e.g. '24' or 'OK')."""
    if is_error:
        return (result_text or "Error")[:60]
    import re
    text = (result_text or "").strip()
    if not text:
        return "—"
    if "Total:" in text or "total" in text.lower():
        m = re.search(r"(\d+)\s*(?:ports?|P-PORT|R-PORT|components?)", text, re.I)
        if m:
            return m.group(1)
    if "No duplicate" in text or "no duplicate" in text.lower():
        return "0"
    if "duplicate" in text.lower():
        m = re.search(r"(\d+)\s*duplicate", text, re.I)
        if m:
            return m.group(1)
    if "No software components" in text or "no software" in text.lower():
        return "0"
    if "found" in text.lower() or "Found" in text:
        m = re.search(r"(\d+)\s*(?:ports?|components?|instances?)", text, re.I)
        if m:
            return m.group(1)
    if "passed" in text.lower() or "valid" in text.lower():
        return "OK"
    return text[:50] + ("..." if len(text) > 50 else "")


def _html_escape(s: str) -> str:
    """Escape for use inside HTML content."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _file_display_name(selected_file):
    """Short display name: strip .arxml, replace spaces with underscores."""
    if not selected_file:
        return ""
    name = selected_file.replace(".arxml", "").replace(".ARXML", "").strip()
    return name.replace(" ", "_")


def _append_chat_history(payload, selected_file):
    """Append a run to agent_chat_history in session state; cap at AGENT_CHAT_HISTORY_MAX."""
    import time
    history = st.session_state.get(AGENT_CHAT_HISTORY_KEY, [])
    entry = {
        "command": (payload.get("command") or "").strip(),
        "file": selected_file or "",
        "timestamp": time.time(),
        "payload": dict(payload),
    }
    history = (history + [entry])[-AGENT_CHAT_HISTORY_MAX:]
    st.session_state[AGENT_CHAT_HISTORY_KEY] = history


def chatbot_interface(upload_dir="uploads"):
    _inject_theme()
    st.subheader("AI Agent")

    os.makedirs(upload_dir, exist_ok=True)

    uploaded_file = st.file_uploader("Upload ARXML", type=None, accept_multiple_files=False, key="agent_arxml_upload")
    if uploaded_file is not None:
        safe_name = safe_upload_filename(uploaded_file.name)
        if not safe_name:
            st.error("Invalid file type or filename. Only .arxml files with a safe name are accepted.")
        else:
            data = uploaded_file.getvalue()
            if len(data) > MAX_UPLOAD_BYTES:
                st.error(f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024*1024)} MB.")
            else:
                path = os.path.join(upload_dir, safe_name)
                with open(path, "wb") as f:
                    f.write(data)
                st.session_state["agent_file_select"] = safe_name
                st.rerun()

    try:
        arxml_files = sorted(f for f in os.listdir(upload_dir) if is_arxml_only(f))
    except FileNotFoundError:
        st.error("Upload directory not found.")
        return
    if not arxml_files:
        st.caption("Upload an .arxml file to start.")
        return

    selected_file = st.selectbox("Select ARXML File", arxml_files, key="agent_file_select")
    input_key = f"{INPUT_KEY_PREFIX}{selected_file}"
    if "_do_clear_chat_input" in st.session_state and st.session_state["_do_clear_chat_input"] == input_key:
        if input_key in st.session_state:
            del st.session_state[input_key]
        del st.session_state["_do_clear_chat_input"]

    if AGENT_LAST_RUN_KEY not in st.session_state:
        st.session_state[AGENT_LAST_RUN_KEY] = None

    col_left, col_right_outer = st.columns([1, 4])
    tool_count = len(get_all_tools())

    with col_left:
        st.markdown("**Project**")
        st.markdown("---")
        st.markdown(f"**File:** {_file_display_name(selected_file)}")
        st.markdown("**Status:** Loaded")
        st.markdown("**Model:** Llama3")
        st.markdown("**Memory:** Active")
        st.markdown(f"**Tools:** {tool_count}")

    last = st.session_state.get(AGENT_LAST_RUN_KEY)
    with col_right_outer:
        inner_center, inner_right = st.columns([3, 1])
        with inner_center:
            st.markdown("**Command**")
            user_query = st.text_input(
                "cmd",
                key=input_key,
                label_visibility="collapsed",
                placeholder="Extract ports, validate UUIDs, compare files, full analysis",
            )
            st.caption("Examples: Extract ports, Validate UUIDs, Compare files, Full analysis")
            run_clicked = st.button("\u25b6 Execute")

            if run_clicked and user_query:
                with st.spinner("Running..."):
                    try:
                        out = process_query_structured(
                            user_query, upload_dir, selected_file=selected_file
                        )
                        st.session_state[AGENT_LAST_RUN_KEY] = out
                        _append_chat_history(out, selected_file)
                        st.session_state["_do_clear_chat_input"] = input_key
                        st.rerun()
                    except Exception as e:
                        out = {
                            "command": user_query,
                            "plan": [],
                            "tool_results": [],
                            "summary": f"Error: {str(e)}",
                            "steps": [],
                        }
                        st.session_state[AGENT_LAST_RUN_KEY] = out
                        _append_chat_history(out, selected_file)
                        st.session_state["_do_clear_chat_input"] = input_key
                        st.rerun()

            st.markdown("**Output**")
            if last:
                cmd = (last.get("command") or "").strip()
                if len(cmd) > 60:
                    cmd = cmd[:57] + "..."
                st.caption(f"Last: {cmd}" if cmd else "Last run")
                if last.get("advisory"):
                    st.info("Advisory (no tools executed)")
                    st.markdown(last.get("summary", ""))
                else:
                    plan = last.get("plan") or []
                    st.markdown("**Plan**")
                    for i, step in enumerate(plan, 1):
                        name = step.get("tool_name", "").replace("_tool", "").replace("_", " ")
                        st.markdown(f"{i}. {name}")
                    if plan:
                        st.markdown(f"{len(plan) + 1}. Summarize")
                    st.markdown("**Results**")
                    for tr in last.get("tool_results") or []:
                        tool_name = tr.get("tool_name", "")
                        label = _TOOL_LABELS.get(tool_name, tool_name.replace("_", " "))
                        val = _result_display_value(
                            tool_name,
                            tr.get("result"),
                            tr.get("error", False),
                        )
                        st.markdown(f"- **{label}:** {val}")
                    st.markdown("**Summary**")
                    st.markdown(last.get("summary", ""))
            else:
                st.caption("Run a command to see results.")

        with inner_right:
            steps = (last or {}).get("steps") if last else []
            step_lines = "".join(f"<div>\u2713 {_html_escape(s)}</div>" for s in steps)
            if not step_lines:
                step_lines = "<div style='color:#e0e0e0;font-size:0.9em;'>Idle</div>"
            st.markdown(
                f'<div id="agent-activity-fossil" style="color:#f0f0f0;"><strong>Agent Activity</strong>'
                f'<hr style="border-color:rgba(255,255,255,0.3);margin:8px 0;">{step_lines}</div>',
                unsafe_allow_html=True,
            )
