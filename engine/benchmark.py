import gc
import json
import os
import tempfile
import time
import tracemalloc
from dataclasses import dataclass, asdict
from statistics import mean, median

from validators.audit_runner import run_audit_validators


@dataclass
class BenchCase:
    name: str
    file_path: str
    size_bytes: int
    runs: int
    durations_ms: list[float]
    peak_memory_kb: float
    pass_count: int
    fail_count: int
    warning_count: int


def _make_sample_arxml(repeat_packages: int) -> str:
    pkg = "<AR-PACKAGE><SHORT-NAME>P{idx}</SHORT-NAME></AR-PACKAGE>"
    body = "".join(pkg.format(idx=i) for i in range(repeat_packages))
    return f"<AUTOSAR><AR-PACKAGES>{body}</AR-PACKAGES></AUTOSAR>"


def _write_temp_file(contents: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".arxml")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contents)
    return path


def _run_case(name: str, file_path: str, runs: int, xsd_path: str | None = None) -> BenchCase:
    durations_ms: list[float] = []
    peak_memory_kb = 0.0
    pass_count = fail_count = warning_count = 0

    for _ in range(runs):
        gc.collect()
        tracemalloc.start()
        t0 = time.perf_counter()
        rows = run_audit_validators(file_path, xsd_path=xsd_path)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        durations_ms.append(elapsed_ms)
        peak_memory_kb = max(peak_memory_kb, peak / 1024.0)
        pass_count = sum(1 for r in rows if r.get("status") == "PASS")
        fail_count = sum(1 for r in rows if r.get("status") == "FAIL")
        warning_count = sum(1 for r in rows if r.get("status") == "WARNING")

    return BenchCase(
        name=name,
        file_path=file_path,
        size_bytes=os.path.getsize(file_path),
        runs=runs,
        durations_ms=durations_ms,
        peak_memory_kb=peak_memory_kb,
        pass_count=pass_count,
        fail_count=fail_count,
        warning_count=warning_count,
    )


def run_audit_benchmark(mode: str = "all", runs: int = 3, xsd_path: str | None = None) -> dict:
    """
    Benchmark audit runner using synthetic ARXML files.
    mode: small | medium | large | all
    """
    mode = (mode or "all").lower()
    size_map = {
        "small": 10,
        "medium": 200,
        "large": 2000,
    }
    selected = ["small", "medium", "large"] if mode == "all" else [mode]
    for m in selected:
        if m not in size_map:
            raise ValueError(f"Invalid mode '{mode}'. Use small|medium|large|all")

    temp_files: list[str] = []
    try:
        cases: list[BenchCase] = []
        for m in selected:
            xml = _make_sample_arxml(size_map[m])
            path = _write_temp_file(xml)
            temp_files.append(path)
            cases.append(_run_case(m, path, runs=runs, xsd_path=xsd_path))

        summaries = []
        for c in cases:
            summaries.append({
                "name": c.name,
                "size_bytes": c.size_bytes,
                "runs": c.runs,
                "latency_ms_avg": round(mean(c.durations_ms), 3),
                "latency_ms_p50": round(median(c.durations_ms), 3),
                "latency_ms_max": round(max(c.durations_ms), 3),
                "peak_memory_kb": round(c.peak_memory_kb, 3),
                "pass_count": c.pass_count,
                "fail_count": c.fail_count,
                "warning_count": c.warning_count,
            })
        return {
            "mode": mode,
            "cases": summaries,
            "generated_at_epoch": int(time.time()),
        }
    finally:
        for p in temp_files:
            if os.path.exists(p):
                os.remove(p)


def benchmark_to_json(mode: str = "all", runs: int = 3, xsd_path: str | None = None) -> str:
    return json.dumps(run_audit_benchmark(mode=mode, runs=runs, xsd_path=xsd_path), indent=2)

