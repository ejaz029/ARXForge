from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any


def _default_output_path(file_path: str, export_format: str, output_dir: str = "reports") -> str:
    os.makedirs(output_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(file_path))[0] or "audit"
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return os.path.join(output_dir, f"audit_report_{stem}_{ts}.{export_format}")


def _to_markdown(rows: list[dict[str, Any]], trace: dict[str, Any], source_file: str) -> str:
    lines = [
        "# ARXForge Audit Report",
        "",
        f"- Source file: `{source_file}`",
        f"- Total duration (ms): `{trace.get('total_duration_ms', 0)}`",
        f"- PASS: `{trace.get('pass_count', 0)}`  FAIL: `{trace.get('fail_count', 0)}`  WARNING: `{trace.get('warning_count', 0)}`",
        "",
        "## Results",
        "",
        "| Validator | Status | Summary |",
        "|---|---|---|",
    ]
    for r in rows:
        safe_summary = str(r.get("summary", "")).replace("|", "\\|")
        lines.append(f"| {r.get('name','')} | {r.get('status','')} | {safe_summary} |")
    lines.extend(["", "## Execution Trace", ""])
    for t in trace.get("validators", []):
        lines.append(
            f"- `{t.get('validator_id','')}` status={t.get('status','')} duration_ms={t.get('duration_ms', 0)}"
        )
    lines.append("")
    return "\n".join(lines)


def export_audit_report(
    *,
    file_path: str,
    rows: list[dict[str, Any]],
    trace: dict[str, Any],
    export_format: str,
    output_path: str | None = None,
) -> dict[str, Any]:
    fmt = (export_format or "").lower()
    if fmt not in ("json", "md", "pdf"):
        raise ValueError("Unsupported export format. Use json|md|pdf")

    output_path = output_path or _default_output_path(file_path, fmt)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    payload = {
        "source_file": file_path,
        "trace": trace,
        "results": rows,
    }
    if fmt == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return {"format": "json", "path": output_path, "bytes": os.path.getsize(output_path)}

    md_text = _to_markdown(rows, trace, file_path)
    if fmt == "md":
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        return {"format": "md", "path": output_path, "bytes": os.path.getsize(output_path)}

    # PDF export (best effort via reportlab)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception as e:
        raise RuntimeError("PDF export requires reportlab dependency") from e

    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    y = height - 40
    for line in md_text.splitlines():
        if y < 40:
            c.showPage()
            y = height - 40
        c.drawString(40, y, line[:140])
        y -= 14
    c.save()
    return {"format": "pdf", "path": output_path, "bytes": os.path.getsize(output_path)}

