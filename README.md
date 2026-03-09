# ARXForge — AUTOSAR ARXML Validator & AI Agent

Copyright (c) 2025 Ejaz Belgaum. Licensed under the MIT License (see LICENSE file for details).

Validate, compare, and analyze AUTOSAR ARXML files with rule-based validators and an AI agent (LangGraph + Groq).

---

## Features

- **AI Agent** — Natural-language commands; LangGraph planning and tool execution; intent routing (extraction, validation, analysis, comparison); 15+ tools (extract SWCs, ports, ECUs, UUIDs; validate schema, data consistency, port refs, component refs, communication, memory, RTE, diagnostics, BSW, version; check duplicate UUIDs/ports); RAG fallback for general questions; session memory and follow-up; deterministic audit report for "complete audit" / "structured report" flows.
- **Compare ARXML** — Structural diff (added/removed/modified), rename detection, categorization (Architecture, Interface, Data Model, Signals, Metadata), severity (HIGH/MEDIUM/LOW), optional LLM engineering summary.
- **ARXML Validator** — Schema validation (XSD), data consistency; upload and run validators from the UI.
- **Upload & View** — Upload `.arxml` files; list and view contents from `uploads/`.

---

## Tech stack

| Component   | Technology                                      |
|------------|--------------------------------------------------|
| Frontend   | Streamlit                                       |
| AI         | LangChain, LangGraph, Groq (e.g. Llama)         |
| RAG        | sentence-transformers, FAISS                    |
| Backend    | Python; `xml.etree.ElementTree` / lxml for ARXML |
| Config     | `config.yaml` (optional `.env` for `GROQ_API_KEY`) |

---

## Folder structure

```
project-root/
├── app/              # Streamlit app (main.py), file utils
├── ai/               # Agent (arxml_agent, agent_tools, intent_router), chatbot UI, RAG, compare_report
├── validators/       # Schema, data consistency, ports, component refs, communication, memory,
│                     # RTE, diagnostics, ECU/BSW, version compatibility, duplicates, compare_arxml
├── config/           # LLM, logging, settings, device utils
├── models/           # Embedding, LLM, anomaly detector
├── tests/            # Pytest tests; run_tests.py for phased runs
├── uploads/          # Uploaded ARXML (gitignored)
├── config.yaml       # App and agent config
├── requirements.txt
├── start_streamlit.ps1   # Optional: free port 8501 and run Streamlit (Windows)
└── README.md
```

---

## Prerequisites and setup

- **Python 3.10+**
- Create a virtual environment and install dependencies:

```bash
pip install -r requirements.txt
```

- **Config**: Create or copy `config.yaml` with `GROQ_API_KEY` (or set `GROQ_API_KEY` in `.env`). Do not commit `config.yaml` if it contains secrets (it is listed in `.gitignore`).

---

## How to run

From the repository root:

```bash
streamlit run app/main.py
```

On Windows you can use the helper script (frees port 8501 and starts Streamlit):

```powershell
.\start_streamlit.ps1
```

Open the app (e.g. http://localhost:8501) and use the sidebar: **AI Agent**, **ARXML Validator**, **Upload & View ARXML**, **Compare ARXML**.

---

## Agent tools

The agent exposes these tools (see `ai/agent_tools.py`):

- **Extraction**: `extract_software_components`, `extract_ports_tool`, `extract_ecu_instances`, `extract_uuids_tool`
- **Validation**: `validate_schema_tool`, `validate_data_consistency_tool`, `validate_port_references_tool`, `validate_component_refs_tool`, `validate_swc_tool`, `validate_communication_tool`, `validate_memory_tool`, `validate_rte_tool`, `validate_diagnostics_tool`, `validate_ecu_bsw_tool`, `validate_version_compatibility_tool`
- **Checks**: `check_duplicate_uuids_tool`, `duplicate_ports_tool`

---

## Example queries (AI Agent)

- "Extract all ports."
- "What are the most critical issues in this file?"
- "Run a complete audit and give validation errors, UUID consistency, risk assessment."
- "Which ports are duplicated?"
- "Generate a structured engineering report."

For comparing two files, use the **Compare ARXML** page: select File A and File B, then click Compare.

---

## Testing

- Run all tests:

```bash
pytest tests/ -v
```

- Phased test run (tools, intent router, planning, tool chaining, etc.):

```bash
python run_tests.py
```

---

## Compare ARXML

On the **Compare ARXML** page, select File A and File B from the files in `uploads/`, then click **Compare**. Results include element/port/SWC counts, added/removed/modified items (with rename detection), hierarchy diff grouped by path, and an optional LLM-generated engineering report.

---

## Repository and license

- **Repository**: [https://github.com/ejaz029/ARXForge](https://github.com/ejaz029/ARXForge)
- **License**: MIT
- **Author / maintainer**: Ejaz Belgaum (ejaz029)

---

## Environment and .gitignore

- **Environment**: Set `GROQ_API_KEY` in `config.yaml` or in a `.env` file.
- **Ignored paths**: `venv/`, `venvZ/`, `config.yaml`, `.env`, `uploads/`, `logs/`, `__pycache__/`, and similar build/artifact paths are in `.gitignore`.
