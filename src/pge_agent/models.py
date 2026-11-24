from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)
    schema_version: Literal["1.0"] = "1.0"


class MaterialInput(Record):
    name: str
    quantity: float | None = Field(default=None, ge=0)
    lead_weeks: float | None = Field(default=None, ge=0)
    need_by: date | None = None


class ProjectRecord(Record):
    project_name: str = ""
    project_number: str = ""
    requestor: str = ""
    project_type: str = ""
    voltage_kv: float | None = Field(default=None, gt=0)
    structures: int | None = Field(default=None, ge=0)
    line_miles: float | None = Field(default=None, ge=0)
    terrain: str | None = None
    hftd_tier: str | None = None
    permitting: str | None = None
    outage_required: bool | None = None
    project_start: date | None = None
    in_service_date: date | None = None
    project_completion: date | None = None
    target_ifc: date | None = None
    construction_start: date | None = None
    project_manager: str | None = None
    core_team: str | None = None
    stakeholders: dict[str, bool | None] = Field(default_factory=dict)
    contracted_engineering: bool | None = None
    materials: list[MaterialInput] = Field(default_factory=list)
    proposed_milestones: dict[str, date] = Field(default_factory=dict)
    engineer_risks: list[str] = Field(default_factory=list)
    scope: str = ""


def fingerprint(project: ProjectRecord) -> str:
    raw = json.dumps(project.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


class DocumentPage(Record):
    page: int = Field(ge=1)
    text: str


class ParsedDocument(Record):
    document_id: str
    name: str
    sha256: str
    pages: list[DocumentPage]
    warnings: list[str] = Field(default_factory=list)


class EvidenceItem(Record):
    evidence_id: str
    field: str
    value: str | float | int | bool | None = None
    units: str | None = None
    original_text: str
    origin: Literal["document", "user", "synthetic"]
    document_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    status: Literal["proposed", "confirmed", "missing", "superseded"] = "proposed"
    reason: str | None = None


class InputIssue(Record):
    field: str
    kind: Literal["missing", "conflict", "unsupported", "warning"]
    question: str
    owner: str
    affected_output: str


class Comparable(Record):
    project_id: str
    hours: float | None = Field(default=None, ge=0)
    similarity: float | None = Field(default=None, ge=0, le=1)
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    basis: Literal["actual", "benchmark", "synthetic"]


class HistoricalContext(Record):
    input_fingerprint: str
    provider_version: str
    status: Literal["available", "unavailable", "demo"]
    comparables: list[Comparable] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Calculation(Record):
    calculation_id: str
    description: str
    value: float | str
    unit: str
    evidence_ids: list[str] = Field(default_factory=list)


class Hours(Record):
    phases: dict[str, float | None] = Field(default_factory=dict)
    total: float | None = Field(default=None, ge=0)
    low: float | None = Field(default=None, ge=0)
    high: float | None = Field(default=None, ge=0)
    confidence: str = "Unavailable"
    notes: str = ""


class Milestone(Record):
    name: str
    requested: date | None = None
    internal_target: date | None = None
    external_forecast: date | None = None
    status: str = "Unavailable"
    notes: str = ""


class Phase(Record):
    name: str
    duration_weeks: float | None = Field(default=None, ge=0)
    hours: float | None = Field(default=None, ge=0)
    key_milestones: str = ""


class MaterialResult(Record):
    name: str
    lead_weeks: float | None = Field(default=None, ge=0)
    need_by: date | None = None
    order_by: date | None = None
    buffered_order_by: date | None = None
    engineering_action_date: date | None = None
    critical_path: str = "Unavailable"
    status: str = "Unavailable"
    notes: str = ""


class Risk(Record):
    description: str
    likelihood: str = "Not assessed"
    impact: str = "Not assessed"
    mitigation: str = "Needs engineer review"
    evidence_ids: list[str] = Field(default_factory=list)


class Resource(Record):
    role: str
    expected_load: str
    notes: str = ""


class Permit(Record):
    name: str
    turnaround_weeks: float | None = Field(default=None, ge=0)
    notes: str = ""


class ForecastResult(Record):
    input_fingerprint: str
    provider_version: str
    status: Literal["available", "unavailable", "demo"]
    rule_version: str = "Unconfirmed"
    schedule_buffer_days: int | None = Field(default=None, ge=0)
    recommended_start: date | None = None
    duration_weeks: float | None = Field(default=None, ge=0)
    buffered_ifc: date | None = None
    schedule_status: str = "Unavailable"
    critical_path_warning: str = "Unavailable"
    critical_path_drivers: list[str] = Field(default_factory=list)
    milestones: list[Milestone] = Field(default_factory=list)
    phases: list[Phase] = Field(default_factory=list)
    hours: Hours = Field(default_factory=Hours)
    materials: list[MaterialResult] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)
    resource_overview: str = "Unavailable"
    capacity_concerns: list[str] = Field(default_factory=list)
    permits: list[Permit] = Field(default_factory=list)
    permitting_summary: str = "Unavailable"
    roadblocks: list[str] = Field(default_factory=list)
    critical_path_summary: str = "Unavailable"
    next_steps: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    calculations: list[Calculation] = Field(default_factory=list)
    numeric_refs: dict[str, str] = Field(default_factory=dict)
    evidence: list[EvidenceItem] = Field(default_factory=list)


class Claim(Record):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)
    assumption: bool = False


class Assessment(Record):
    summary: list[Claim]
    next_steps: list[str]
    limitations: list[str]


class AssessmentRun(Record):
    report_edits: dict[str, str] = Field(default_factory=dict)
    run_id: str = Field(default_factory=lambda: uuid4().hex)
    parent_run_id: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    review_status: Literal["draft", "reviewed"] = "draft"
    reviewed_at: datetime | None = None
    reviewer: str | None = None
    project: ProjectRecord
    documents: list[ParsedDocument] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    issues: list[InputIssue]
    history: HistoricalContext
    forecast: ForecastResult
    assessment: Assessment
    validation_errors: list[str]
    demo: bool = False
    versions: dict[str, str] = Field(default_factory=dict)
