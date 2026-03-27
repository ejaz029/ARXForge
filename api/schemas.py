from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class AuditRequest(BaseModel):
    file_path: str
    xsd_path: str | None = None


class TraceEntry(BaseModel):
    validator_id: str
    name: str
    status: str
    duration_ms: float


class ExecutionTrace(BaseModel):
    file: str
    total_duration_ms: float
    pass_count: int
    fail_count: int
    warning_count: int
    validators: list[TraceEntry]


class CompareRequest(BaseModel):
    file_a: str
    file_b: str


class GraphRequest(BaseModel):
    file_path: str


class AuditExportRequest(BaseModel):
    file_path: str
    xsd_path: str | None = None
    export_format: str
    output_path: str | None = None

