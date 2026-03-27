import os
from typing import Any

# Lazy imports: audit_runner pulls the full validator + plugin tree; loading it at import time
# blocks Streamlit before main() can render anything (blank "RUNNING…" screen).


def run_full_audit(file_path: str, xsd_path: str | None = None) -> list[dict[str, Any]]:
    from validators.audit_runner import run_audit_validators

    return run_audit_validators(file_path, xsd_path)


def run_compare(file_a: str, file_b: str) -> dict[str, Any]:
    from validators.compare_arxml import compare_two_arxml_files

    return compare_two_arxml_files(file_a, file_b)


def run_graph(file_path: str) -> dict[str, Any]:
    from validators.arxml_graph import build_arxml_graph

    graph_data, err = build_arxml_graph(file_path)
    if err:
        return {"error": err}
    return {"graph": graph_data}


def resolve_upload_file(upload_dir: str, filename_or_path: str) -> str:
    """Resolve filename from uploads safely; fallback to direct path for trusted internal calls."""
    # Prevent traversal via uploaded filename route.
    safe_name = os.path.basename((filename_or_path or "").strip())
    if safe_name and safe_name == filename_or_path:
        candidate = os.path.join(upload_dir, safe_name)
        if os.path.exists(candidate):
            return candidate
    return filename_or_path

