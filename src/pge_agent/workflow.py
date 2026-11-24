from .adapters import TemplateWriter, UnavailableForecaster, UnavailableRetriever
from .models import AssessmentRun, InputIssue
from .validation import input_issues, validate_results


def generate(project, evidence=None, documents=None, retriever=None, forecaster=None,
             writer=None, parent_run_id=None, allow_demo=False):
    evidence = list(evidence or [])
    documents = list(documents or [])
    retriever = retriever or UnavailableRetriever()
    forecaster = forecaster or UnavailableForecaster()
    writer = writer or TemplateWriter()
    failures = []
    try:
        history = retriever.retrieve(project)
    except Exception as exc:
        history = UnavailableRetriever().retrieve(project)
        failures.append(f"Group 1 response could not be validated ({type(exc).__name__}).")
    try:
        forecast = forecaster.forecast(project, history)
    except Exception as exc:
        forecast = UnavailableForecaster().forecast(project, history)
        failures.append(f"Group 2 response could not be validated ({type(exc).__name__}).")
    demo = history.status == "demo" or forecast.status == "demo"
    if demo and (not allow_demo or documents or any(e.origin == "document" for e in evidence)):
        raise ValueError("Synthetic results are allowed only in an explicit demo without real AA documents.")
    evidence += history.evidence + forecast.evidence
    assessment = writer.draft(project, history, forecast)
    issues = input_issues(project, evidence)
    issues.append(InputIssue(field="schedule_buffer", kind="warning", owner="Group 2 / PG&E",
        question="Reconcile the mockup's 30-day buffer with the newer 45-day meeting-note guidance.",
        affected_output="Schedule buffer and forecast dates"))
    errors = failures + validate_results(project, history, forecast, assessment, evidence)
    docs = {d.document_id: d for d in documents}
    for e in evidence:
        if e.origin != "document":
            continue
        doc = docs.get(e.document_id)
        page = next((p for p in doc.pages if p.page == e.page), None) if doc else None
        if page is None or not e.original_text.strip() or e.original_text not in page.text:
            errors.append(f"Evidence {e.evidence_id} does not resolve to its source page and excerpt.")
    return AssessmentRun(project=project, parent_run_id=parent_run_id, documents=documents,
        evidence=evidence, history=history, forecast=forecast, assessment=assessment,
        issues=issues, validation_errors=errors, demo=demo,
        versions={"workflow":"1.0", "writer":getattr(writer,"version","external"),
                  "history":history.provider_version,"forecast":forecast.provider_version})


def compare_runs(old, new):
    changes = []
    def diff(a, b, path):
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(a.keys() | b.keys()):
                if key not in {"input_fingerprint", "calculations", "numeric_refs"}:
                    diff(a.get(key), b.get(key), f"{path}.{key}")
        elif a != b:
            changes.append({"field":path,"before":a,"after":b})
    for section in ("project", "forecast", "issues", "validation_errors"):
        diff(old.model_dump(mode="json")[section],new.model_dump(mode="json")[section],section)
    return changes
