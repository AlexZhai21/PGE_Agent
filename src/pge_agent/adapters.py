"""Stable component boundaries; no network calls or implicit model execution."""
from pathlib import Path
from typing import Protocol

from .models import (Assessment, Claim, ForecastResult, HistoricalContext,
                     ProjectRecord, fingerprint)


class HistoricalRetriever(Protocol):
    def retrieve(self, project: ProjectRecord) -> HistoricalContext: ...


class ForecastEngine(Protocol):
    def forecast(self, project: ProjectRecord, history: HistoricalContext) -> ForecastResult: ...


class AssessmentWriter(Protocol):
    def draft(self, project: ProjectRecord, history: HistoricalContext,
              forecast: ForecastResult) -> Assessment: ...


class UnavailableRetriever:
    def retrieve(self, project):
        return HistoricalContext(input_fingerprint=fingerprint(project), provider_version="unavailable-1",
            status="unavailable", limitations=["Group 1 integration has not supplied comparable projects."])


class UnavailableForecaster:
    def forecast(self, project, history):
        return ForecastResult(input_fingerprint=fingerprint(project), provider_version="unavailable-1",
            status="unavailable", assumptions=["Group 2 integration has not supplied a supported forecast."])


class JsonRetriever:
    def __init__(self, data: str):
        self.data = data

    def retrieve(self, project):
        return HistoricalContext.model_validate_json(self.data)


class JsonForecaster:
    def __init__(self, data: str):
        self.data = data

    def forecast(self, project, history):
        return ForecastResult.model_validate_json(self.data)


class FixtureRetriever:
    def __init__(self, scenario):
        self.scenario = scenario

    def retrieve(self, project):
        if fingerprint(project) == fingerprint(self.scenario.project):
            return self.scenario.history.model_copy(deep=True)
        return UnavailableRetriever().retrieve(project)


class FixtureForecaster:
    def __init__(self, scenario):
        self.scenario = scenario

    def forecast(self, project, history):
        if fingerprint(project) == fingerprint(self.scenario.project):
            return self.scenario.forecast.model_copy(deep=True)
        return UnavailableForecaster().forecast(project, history)


class TemplateWriter:
    version = "template-writer-1"

    def draft(self, project, history, forecast):
        summary = []
        if forecast.status == "unavailable":
            summary.append(Claim(text="Forecast results are unavailable. Complete the open inputs and connect supported component results.", assumption=True))
        elif forecast.hours.total is not None:
            summary.append(Claim(text=f"The supplied engineering forecast totals {forecast.hours.total:g} hours.",
                                 calculation_ids=[forecast.numeric_refs.get("hours.total", "missing")]))
        if history.comparables:
            summary.append(Claim(text="Historical comparisons are listed with their selection rationale and source basis.",
                                 evidence_ids=[i for c in history.comparables for i in c.evidence_ids]))
        limitations = list(history.limitations) + list(forecast.assumptions)
        if forecast.status == "demo" or history.status == "demo":
            limitations.insert(0, "Synthetic demonstration only; these results are not a PG&E forecast.")
        return Assessment(summary=summary, next_steps=forecast.next_steps or [
            "Review source facts and resolve open questions.",
            "Obtain supported historical context and forecasting results from Groups 1 and 2."],
            limitations=limitations)
