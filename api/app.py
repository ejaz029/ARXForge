import os
import time
import asyncio
from collections import defaultdict, deque
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from api.schemas import HealthResponse, AuditRequest, CompareRequest, GraphRequest, AuditExportRequest
from engine.services import run_full_audit, run_compare, run_graph, resolve_upload_file
from engine.report_export import export_audit_report


APP_VERSION = "1.0.0"
MAX_REQUEST_BYTES = int(os.getenv("ARXFORGE_API_MAX_REQUEST_BYTES", str(2 * 1024 * 1024)))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("ARXFORGE_API_TIMEOUT_SECONDS", "30"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("ARXFORGE_API_RATE_LIMIT_PER_MINUTE", "120"))

_rate_limiter: dict[str, deque] = defaultdict(deque)

app = FastAPI(title="ARXForge API", version=APP_VERSION)


@app.middleware("http")
async def safety_middleware(request: Request, call_next):
    # Request size guard
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_REQUEST_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"error": "REQUEST_TOO_LARGE", "message": "Payload exceeds API limit."},
                )
        except ValueError:
            pass

    # Basic in-memory rate limiting hook (per client IP, per minute)
    client = request.client.host if request.client else "unknown"
    now = time.time()
    window = _rate_limiter[client]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        return JSONResponse(
            status_code=429,
            content={"error": "RATE_LIMITED", "message": "Too many requests. Try again shortly."},
        )
    window.append(now)

    # Timeout guard
    try:
        return await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={"error": "REQUEST_TIMEOUT", "message": "Request timed out."},
        )


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", service="arxforge-api", version=APP_VERSION)


@app.post("/audit")
def audit(payload: AuditRequest):
    started = time.perf_counter()
    rows = run_full_audit(payload.file_path, payload.xsd_path)
    trace_validators = [
        {
            "validator_id": r.get("validator_id", ""),
            "name": r.get("name", ""),
            "status": r.get("status", ""),
            "duration_ms": float(r.get("duration_ms", 0.0)),
        }
        for r in rows
    ]
    trace = {
        "file": payload.file_path,
        "total_duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "pass_count": sum(1 for r in rows if r.get("status") == "PASS"),
        "fail_count": sum(1 for r in rows if r.get("status") == "FAIL"),
        "warning_count": sum(1 for r in rows if r.get("status") == "WARNING"),
        "validators": trace_validators,
    }
    return {"result": rows, "trace": trace}


@app.post("/compare")
def compare(payload: CompareRequest):
    result = run_compare(payload.file_a, payload.file_b)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {"result": result}


@app.post("/graph")
def graph(payload: GraphRequest):
    result = run_graph(payload.file_path)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {"result": result}


@app.post("/audit/uploaded/{filename}")
def audit_uploaded(filename: str):
    upload_dir = os.getenv("ARXFORGE_UPLOAD_DIR", "uploads")
    file_path = resolve_upload_file(upload_dir, filename)
    started = time.perf_counter()
    rows = run_full_audit(file_path)
    trace_validators = [
        {
            "validator_id": r.get("validator_id", ""),
            "name": r.get("name", ""),
            "status": r.get("status", ""),
            "duration_ms": float(r.get("duration_ms", 0.0)),
        }
        for r in rows
    ]
    trace = {
        "file": file_path,
        "total_duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "pass_count": sum(1 for r in rows if r.get("status") == "PASS"),
        "fail_count": sum(1 for r in rows if r.get("status") == "FAIL"),
        "warning_count": sum(1 for r in rows if r.get("status") == "WARNING"),
        "validators": trace_validators,
    }
    return {"result": rows, "trace": trace}


@app.post("/audit/export")
def audit_export(payload: AuditExportRequest):
    started = time.perf_counter()
    rows = run_full_audit(payload.file_path, payload.xsd_path)
    trace_validators = [
        {
            "validator_id": r.get("validator_id", ""),
            "name": r.get("name", ""),
            "status": r.get("status", ""),
            "duration_ms": float(r.get("duration_ms", 0.0)),
        }
        for r in rows
    ]
    trace = {
        "file": payload.file_path,
        "total_duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "pass_count": sum(1 for r in rows if r.get("status") == "PASS"),
        "fail_count": sum(1 for r in rows if r.get("status") == "FAIL"),
        "warning_count": sum(1 for r in rows if r.get("status") == "WARNING"),
        "validators": trace_validators,
    }
    try:
        artifact = export_audit_report(
            file_path=payload.file_path,
            rows=rows,
            trace=trace,
            export_format=payload.export_format,
            output_path=payload.output_path,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"result": rows, "trace": trace, "artifact": artifact}

