from datetime import date
from math import isclose
from pydantic import BaseModel

from .models import InputIssue, fingerprint


def quantitative_values(result):
    """Output-path => quantitative value, excluding provenance metadata."""
    values = {}
    def visit(value, path):
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="python")
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"schema_version", "calculations", "numeric_refs", "evidence"}:
                    continue
                visit(item, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}.{index}")
        elif isinstance(value, date):
            values[path] = value.isoformat()
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            values[path] = value
    visit(result, "")
    return values


def input_issues(project, evidence):
    issues = []
    required = {
        "project_name": ("Project engineer", "Report identity"),
        "project_type": ("Project engineer", "Applicable rules and comparables"),
        "voltage_kv": ("Project engineer", "Historical matching"),
        "target_ifc": ("Project manager", "IFC feasibility"),
        "construction_start": ("Project manager", "Material and schedule feasibility"),
        "contracted_engineering": ("Project engineer", "Contracting schedule"),
    }
    for field, (owner, impact) in required.items():
        value = getattr(project, field)
        if value is None or value == "":
            issues.append(InputIssue(field=field, kind="missing", question=f"Please provide {field.replace('_', ' ')}.",
                                     owner=owner, affected_output=impact))
    for stakeholder, value in project.stakeholders.items():
        if value is None:
            issues.append(InputIssue(field=f"stakeholders.{stakeholder}", kind="missing",
                question=f"Is {stakeholder} required?", owner="Project engineer", affected_output="Stakeholder schedule and scope impacts"))
    for material in project.materials:
        if material.lead_weeks is None:
            issues.append(InputIssue(field="materials", kind="missing", question=f"Confirm lead time for {material.name}.",
                owner="Supply Chain", affected_output="Material order-by date"))
    for field in {e.field for e in evidence if e.status == "proposed"}:
        candidates = {str(e.value) for e in evidence if e.field == field and e.status == "proposed" and e.value is not None}
        current = getattr(project, field, None)
        if len(candidates) > 1 or (current not in (None, "") and candidates and str(current) not in candidates):
            issues.append(InputIssue(field=field, kind="conflict", question=f"Resolve competing values for {field}.",
                owner="Project engineer", affected_output="Input reliability"))
        else:
            issues.append(InputIssue(field=field, kind="warning", question=f"Confirm the extracted {field} suggestion.",
                owner="Project engineer", affected_output="Input reliability"))
    for field in {e.field for e in evidence if e.status == "missing"}:
        if getattr(project, field, None) in (None, ""):
            issues.append(InputIssue(field=field, kind="missing", question=f"The AA leaves {field} unresolved. Who can supply it?",
                owner="Project engineer", affected_output="Project completeness"))
    if project.target_ifc and project.construction_start and project.target_ifc > project.construction_start:
        issues.append(InputIssue(field="target_ifc", kind="conflict", question="IFC is requested after construction starts; confirm or revise these dates.",
            owner="Project manager", affected_output="Schedule feasibility"))
    if any(term in (project.project_type + " " + project.project_name).lower() for term in ("mpac", "substation")):
        issues.append(InputIssue(field="project_type", kind="unsupported", question="Confirm a substation-specific forecasting integration; pole-project rules are not applicable by default.",
            owner="Group 2 / project engineer", affected_output="Forecast applicability"))
    return issues


def validate_results(project, history, forecast, assessment, evidence):
    errors = []
    expected = fingerprint(project)
    for label, result in (("Group 1", history), ("Group 2", forecast)):
        if result.input_fingerprint != expected:
            errors.append(f"{label} result belongs to different inputs; rerun the component.")
    ids = [e.evidence_id for e in evidence]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate evidence identifiers.")
    evidence_ids = set(ids)
    calculations = {c.calculation_id: c for c in forecast.calculations}
    if len(calculations) != len(forecast.calculations):
        errors.append("Duplicate calculation identifiers.")
    for owner, refs in [(c.project_id, c.evidence_ids) for c in history.comparables] + [
        (c.calculation_id, c.evidence_ids) for c in forecast.calculations] + [
        (r.description, r.evidence_ids) for r in forecast.risks] + [
        (c.text, c.evidence_ids) for c in assessment.summary]:
        if set(refs) - evidence_ids:
            errors.append(f"Unresolved evidence reference: {owner}.")
    for comparable in history.comparables:
        if not comparable.evidence_ids:
            errors.append(f"Comparable {comparable.project_id} has no source evidence.")
    for claim in assessment.summary:
        if set(claim.calculation_ids) - set(calculations):
            errors.append("Assessment references an unknown calculation.")
        if not claim.assumption and not claim.calculation_ids and not claim.evidence_ids:
            errors.append("Assessment claim has no evidence or explicit assumption.")
    for path, value in quantitative_values(forecast).items():
        calc = calculations.get(forecast.numeric_refs.get(path, ""))
        if calc is None:
            errors.append(f"Missing calculation reference for {path}.")
        elif isinstance(value, (float, int)) and isinstance(calc.value, (float, int)):
            if not isclose(value, calc.value, rel_tol=1e-8, abs_tol=1e-6):
                errors.append(f"Calculation mismatch for {path}.")
        elif str(value) != str(calc.value):
            errors.append(f"Calculation mismatch for {path}.")
    h = forecast.hours
    if any(v is not None and v < 0 for v in h.phases.values()):
        errors.append("Phase hours cannot be negative.")
    if h.total is not None and h.phases and all(v is not None for v in h.phases.values()):
        if not isclose(sum(h.phases.values()), h.total, abs_tol=.01):
            errors.append("Phase hours do not sum to the reported total.")
    if h.low is not None and h.high is not None and h.low > h.high:
        errors.append("Hour range is reversed.")
    if h.total is not None and ((h.low is not None and h.total < h.low) or (h.high is not None and h.total > h.high)):
        errors.append("Expected hours fall outside the reported range.")
    if forecast.status == "unavailable" and quantitative_values(forecast):
        errors.append("Unavailable forecast contains numerical results.")
    return errors
