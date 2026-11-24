import argparse
import json
from pathlib import Path

from . import models
from .adapters import FixtureForecaster, FixtureRetriever, JsonForecaster, JsonRetriever
from .demo import scenario
from .intake import DocumentParser, FactExtractor
from .models import ProjectRecord
from .reporting import render_report
from .storage import RunStore
from .workflow import generate


def main():
    parser = argparse.ArgumentParser(description="Local Group 3 prototype")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--scenario", choices=["complete","missing","conflict"], default="complete")
    demo.add_argument("--output", default=".local/exports")
    run = sub.add_parser("run")
    run.add_argument("--project", required=True)
    run.add_argument("--aa")
    run.add_argument("--history")
    run.add_argument("--forecast")
    run.add_argument("--output", default=".local/exports")
    sub.add_parser("schemas")
    args = parser.parse_args()
    if args.command == "schemas":
        output = Path("docs/schemas")
        output.mkdir(parents=True, exist_ok=True)
        for name in ("ProjectRecord","EvidenceItem","InputIssue","HistoricalContext","ForecastResult","AssessmentRun"):
            (output / f"{name}.json").write_text(json.dumps(getattr(models,name).model_json_schema(),indent=2))
        print(output)
        return
    store = RunStore()
    if args.command == "demo":
        sample = scenario(args.scenario)
        result = generate(sample.project, retriever=FixtureRetriever(sample),
                          forecaster=FixtureForecaster(sample), allow_demo=True)
    else:
        project = ProjectRecord.model_validate_json(Path(args.project).read_text())
        documents, evidence = [], []
        if args.aa:
            data = Path(args.aa).read_bytes()
            document = DocumentParser().parse(data,Path(args.aa).name)
            store.save_document(data)
            documents.append(document)
            evidence = FactExtractor().extract(document)
        result = generate(project, documents=documents, evidence=evidence,
            retriever=JsonRetriever(Path(args.history).read_text()) if args.history else None,
            forecaster=JsonForecaster(Path(args.forecast).read_text()) if args.forecast else None)
    store.save(result)
    output = Path(args.output) / result.run_id
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.html").write_text(render_report(result))
    (output / "assessment.json").write_text(result.model_dump_json(indent=2))
    print(f"Run: {result.run_id}\nHTML and JSON: {output}\nValidation errors: {len(result.validation_errors)}")
    if result.validation_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
