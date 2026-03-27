from engine.benchmark import run_audit_benchmark


def test_benchmark_output_schema_small_mode():
    out = run_audit_benchmark(mode="small", runs=1, xsd_path="D:/does/not/exist.xsd")
    assert out["mode"] == "small"
    assert "cases" in out and isinstance(out["cases"], list)
    assert len(out["cases"]) == 1
    case = out["cases"][0]
    required = {
        "name",
        "size_bytes",
        "runs",
        "latency_ms_avg",
        "latency_ms_p50",
        "latency_ms_max",
        "peak_memory_kb",
        "pass_count",
        "fail_count",
        "warning_count",
    }
    assert required.issubset(set(case.keys()))


def test_benchmark_all_mode_has_three_cases():
    out = run_audit_benchmark(mode="all", runs=1, xsd_path="D:/does/not/exist.xsd")
    names = [c["name"] for c in out["cases"]]
    assert names == ["small", "medium", "large"]

