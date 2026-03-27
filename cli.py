#!/usr/bin/env python3
"""
ARXForge CLI: run audit or compare from the command line for CI/CD.
Usage:
  python cli.py audit file.arxml [--xsd path] [--no-fail]
  python cli.py compare a.arxml b.arxml [--report summary]
Exit code: 0 on success / no critical issues; 1 if audit has FAIL (unless --no-fail).
"""
import argparse
import os
import sys
import json


def _ensure_path():
    """Add project root to path so validators can be imported."""
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)


def cmd_audit(
    file_path: str,
    xsd_path: str | None,
    fail_on_error: bool,
    output_format: str = "text",
) -> int:
    """Run full audit on file; optionally emit JSON; exit 1 when fail_on_error and critical issues exist."""
    _ensure_path()
    from validators.audit_runner import run_audit_validators

    if not os.path.isfile(file_path):
        if output_format == "json":
            print(json.dumps({"error": f"File not found: {file_path}"}, indent=2))
        else:
            print(f"CRITICAL: File not found: {file_path}", file=sys.stderr)
        return 1

    results = run_audit_validators(file_path, xsd_path)
    critical = sum(1 for r in results if r.get("status") == "FAIL")
    warnings = sum(1 for r in results if r.get("status") == "WARNING")
    passed = sum(1 for r in results if r.get("status") == "PASS")

    if output_format == "json":
        print(
            json.dumps(
                {
                    "summary": {
                        "critical": critical,
                        "warning": warnings,
                        "pass": passed,
                    },
                    "results": results,
                },
                indent=2,
            )
        )
    else:
        print(f"CRITICAL: {critical} issues")
        print(f"WARNING: {warnings} issues")
        print(f"PASS: {passed} checks")
        for r in results:
            status = r.get("status", "")
            name = r.get("name", "")
            summary = r.get("summary", "")
            sym = "✔" if status == "PASS" else ("❌" if status == "FAIL" else "⚠")
            print(f"  {sym} {name}: {summary}")

    if critical and fail_on_error:
        return 1
    return 0


def cmd_audit_export(file_path: str, xsd_path: str | None, export_format: str, output: str | None) -> int:
    """Run audit and export deterministic report artifact."""
    _ensure_path()
    from validators.audit_runner import run_audit_validators
    from engine.report_export import export_audit_report

    if not os.path.isfile(file_path):
        print(f"CRITICAL: File not found: {file_path}", file=sys.stderr)
        return 1

    rows = run_audit_validators(file_path, xsd_path)
    trace = {
        "file": file_path,
        "total_duration_ms": 0.0,
        "pass_count": sum(1 for r in rows if r.get("status") == "PASS"),
        "fail_count": sum(1 for r in rows if r.get("status") == "FAIL"),
        "warning_count": sum(1 for r in rows if r.get("status") == "WARNING"),
        "validators": [
            {
                "validator_id": r.get("validator_id", ""),
                "name": r.get("name", ""),
                "status": r.get("status", ""),
                "duration_ms": float(r.get("duration_ms", 0.0)),
            }
            for r in rows
        ],
    }
    try:
        artifact = export_audit_report(
            file_path=file_path,
            rows=rows,
            trace=trace,
            export_format=export_format,
            output_path=output,
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"Exported {artifact['format']} report: {artifact['path']} ({artifact['bytes']} bytes)")
    return 0


def cmd_compare(path_a: str, path_b: str, report: str) -> int:
    """Compare two ARXML files; optionally print summary. Exit 0 (compare does not fail build by default)."""
    _ensure_path()
    from validators.compare_arxml import compare_two_arxml_files

    if not os.path.isfile(path_a):
        print(f"Error: File not found: {path_a}", file=sys.stderr)
        return 1
    if not os.path.isfile(path_b):
        print(f"Error: File not found: {path_b}", file=sys.stderr)
        return 1

    out = compare_two_arxml_files(path_a, path_b)
    if out.get("error"):
        print(f"Error: {out['error']}", file=sys.stderr)
        return 1

    summary = out.get("summary", "")
    print(summary)
    if report == "summary" and out.get("summary_counts"):
        sc = out["summary_counts"]
        print(f"Changes: {sc.get('total', 0)} total; "
              f"architecture: {sc.get('architecture', 0)}, interfaces: {sc.get('interfaces', 0)}, "
              f"data_model: {sc.get('data_model', 0)}, signals: {sc.get('signals', 0)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ARXForge CLI — audit or compare ARXML files")
    sub = parser.add_subparsers(dest="command", required=True)

    audit_p = sub.add_parser("audit", help="Run full validation on an ARXML file")
    audit_p.add_argument("file", help="Path to ARXML file")
    audit_p.add_argument("--xsd", default=None, help="Path to XSD schema (default: project AUTOSAR_schema.xsd)")
    audit_p.add_argument("--no-fail", action="store_true", help="Do not exit 1 on critical issues")
    audit_p.add_argument("--fail-on-error", action="store_true", help="Exit 1 if any critical issue exists")
    audit_p.add_argument("--output", choices=["text", "json"], default="text", help="Audit output format")
    audit_p.set_defaults(
        func=lambda a: cmd_audit(
            a.file,
            a.xsd,
            fail_on_error=(True if a.fail_on_error else not a.no_fail),
            output_format=a.output,
        )
    )

    audit_export_p = sub.add_parser("audit-export", help="Run audit and export report artifact")
    audit_export_p.add_argument("file", help="Path to ARXML file")
    audit_export_p.add_argument("--xsd", default=None, help="Path to XSD schema")
    audit_export_p.add_argument("--format", choices=["json", "md", "pdf"], default="json", help="Export format")
    audit_export_p.add_argument("--output", default=None, help="Output file path")
    audit_export_p.set_defaults(func=lambda a: cmd_audit_export(a.file, a.xsd, a.format, a.output))

    compare_p = sub.add_parser("compare", help="Compare two ARXML files")
    compare_p.add_argument("file_a", help="Path to first ARXML file")
    compare_p.add_argument("file_b", help="Path to second ARXML file")
    compare_p.add_argument("--report", choices=["summary"], default="summary", help="Output level (default: summary)")
    compare_p.set_defaults(func=lambda a: cmd_compare(a.file_a, a.file_b, a.report))

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
