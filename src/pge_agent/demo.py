"""Explicit static demonstration fixtures. None of these values are estimating rules."""
from dataclasses import dataclass
from datetime import date

from .models import (Calculation, Comparable, EvidenceItem, ForecastResult, HistoricalContext,
                     Hours, MaterialInput, MaterialResult, Milestone, Phase, ProjectRecord,
                     Resource, Risk, fingerprint)
from .validation import quantitative_values

STAKEHOLDERS = ["Transmission planning", "Distribution planning", "Transmission operations",
                "Distribution operations", "Fiber engineering", "Substation engineering"]

@dataclass
class Scenario:
    project: ProjectRecord
    history: HistoricalContext
    forecast: ForecastResult


def scenario(name="complete") -> Scenario:
    project = ProjectRecord(project_name="SYNTHETIC - Cedar Line Demo", project_number="DEMO-001",
        requestor="Demo engineer", project_type="T-line pole replacement", voltage_kv=115,
        structures=10, line_miles=1.5, terrain="Flat", hftd_tier="Not specified",
        permitting="Engineer review required", outage_required=True,
        target_ifc=date(2027,6,1), construction_start=date(2028,2,1),
        contracted_engineering=False, stakeholders={s: False for s in STAKEHOLDERS},
        materials=[MaterialInput(name="Synthetic conductor", lead_weeks=12, need_by=date(2027,7,6))])
    if name == "missing":
        project.construction_start = None
        project.materials[0].lead_weeks = None
    elif name == "conflict":
        project.construction_start = date(2027,5,1)
    elif name != "complete":
        raise ValueError("Unknown demonstration scenario")
    fp = fingerprint(project)
    evidence = EvidenceItem(evidence_id="demo-basis", field="fixture", value="synthetic",
        original_text="Invented example: 100 total hours allocated 10/20/30/25/10/5; illustrative dates only.",
        origin="synthetic", status="confirmed")
    history = HistoricalContext(input_fingerprint=fp, provider_version="demo-history-1", status="demo",
        evidence=[evidence], comparables=[Comparable(project_id="SYNTHETIC-PAST-01", hours=100,
            similarity=.8, rationale="Invented matching project for integration demonstration only.",
            evidence_ids=["demo-basis"], basis="synthetic")], limitations=["No real historical project was retrieved."])
    forecast = ForecastResult(input_fingerprint=fp, provider_version="demo-forecast-1", status="demo",
        rule_version="synthetic-fixture-1", recommended_start=date(2027,1,4),
        duration_weeks=20, buffered_ifc=date(2027,4,17), schedule_buffer_days=45,
        schedule_status="Illustrative dates; not a feasibility determination",
        critical_path_warning="Confirm all dates with a supported forecasting engine.",
        hours=Hours(phases={"Scoping":10,"30% Design":20,"60% Design":30,"90% / IFC":25,
                          "Construction Support":10,"Closeout":5},total=100,low=80,high=120,
                    confidence="Illustrative; not calibrated",notes="Synthetic phase allocation."),
        milestones=[Milestone(name="Internal IFC Complete", internal_target=date(2027,4,17),
                              external_forecast=date(2027,6,1),status="Synthetic")],
        phases=[Phase(name="Design",duration_weeks=20,hours=85,key_milestones="Synthetic design milestones")],
        resources=[Resource(role="Engineer",expected_load="Needs capacity review",notes="No FTE estimate")],
        risks=[Risk(description="Unconfirmed material lead time",likelihood="Not assessed",
                    impact="May affect construction",mitigation="Confirm with Supply Chain",evidence_ids=["demo-basis"])],
        assumptions=["All numbers and dates are invented fixtures, not approved PG&E rules.",
                     "The template's 30-day buffer and meeting notes' 45-day buffer require reconciliation."],
        next_steps=["Review input facts and replace demonstration adapters with supported components."])
    if name == "complete":
        forecast.materials=[MaterialResult(name="Synthetic conductor",lead_weeks=12,
            need_by=date(2027,7,6),order_by=date(2027,4,13),buffered_order_by=date(2027,3,30),
            status="Synthetic",critical_path="Needs review")]
    if name == "missing":
        forecast.schedule_status="Incomplete: construction date and material lead time missing"
        forecast.recommended_start=None
        forecast.buffered_ifc=None
        forecast.duration_weeks=None
        forecast.milestones=[]
        forecast.phases=[]
    if name == "conflict":
        forecast.schedule_status="Conflict: requested IFC follows construction start"
        forecast.critical_path_warning="Requested dates preserved; engineer confirmation required."
    for index, (path, value) in enumerate(quantitative_values(forecast).items()):
        calc_id=f"fixture-{index}"
        forecast.calculations.append(Calculation(calculation_id=calc_id,description=f"Static synthetic fixture: {path}",
            value=value,unit="date" if isinstance(value,str) else "see output field",evidence_ids=["demo-basis"]))
        forecast.numeric_refs[path]=calc_id
    return Scenario(project,history,forecast)
