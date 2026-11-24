# T-Line Forecast Agent — Group 3 prototype

Local project intake, evidence review, integration with Groups 1 and 2, and report generation for the Berkeley DSS project. The report follows the **Project_Report_Template_MOCKUP.pdf** in the shared **PGE-DOCUMENTATION / Project Level Data** folder.

**This is a framework, not a working PG&E forecasting model.** It makes no model-provider calls. Only explicitly selected synthetic examples have built-in forecast results. Real project reports show unavailable outputs until supported Group 1/2 adapters are connected.

## Run locally

Python 3.11+ (verified with Python 3.13 on macOS):

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

For the exact dependency versions used during validation, install `requirements-tested.txt` before the editable package. This snapshot is tested on macOS/Python 3.13, not a guarantee of compatibility with every platform.

1. Choose **Load demonstration** to try complete, missing-input, or conflicting-input scenarios. Alternatively start a new project and upload an AA PDF.
2. Review extracted field suggestions and accept supported values. Complete the form; unknown fields remain unknown.
3. Generate the report. Optionally upload Group 1/2 JSON responses using the integration contracts.
4. Download HTML and assessment JSON. Open HTML in a browser and print to PDF using Letter paper, background graphics enabled, and browser headers/footers disabled.
5. Edit inputs and generate again. The new run retains its parent; compare them in Revisions. Open saved runs from the sidebar after refreshing.

Review status records a local engineer review; it is not authentication, formal approval, or publication. Validation errors and unresolved input conflicts block marking a run reviewed. A reviewed demonstration remains a demonstration.

## Command-line examples

```sh
pge-agent demo --scenario complete
pge-agent demo --scenario missing
pge-agent demo --scenario conflict
pge-agent run --project examples/manual-project.json
pge-agent run --project examples/manual-project.json --aa /path/to/authorization.pdf
pge-agent schemas
pytest -q
```

Results and the SQLite database are stored under `.local/` (override with `PGE_AGENT_DATA_DIR`). Uploaded documents use content-hash filenames. `.local/`, credentials, and generated artifacts are excluded from Git. Do not add PG&E source documents or generated real-project reports to the repository.

## Ownership and integration

- **Group 1:** similar historical projects, associated hours, selection rationale, and source evidence.
- **Group 2:** engineering-hour forecasts, milestone dates, material deadlines, risks, and rule/calculation basis.
- **Group 3:** intake, source tracking, component coordination, validation, reporting, and revision history.

See [integration contracts](docs/integration.md), [architecture](docs/architecture.md), and the JSON Schemas in `docs/schemas/`. The UI exports the reviewed project record and displays its fingerprint. An adapter response must match that fingerprint, preventing stale results from being treated as current.

A static fixture matches its original project record exactly. Editing it returns unavailable component results, intentionally demonstrating invalidation rather than pretending to recalculate. A real forecasting adapter supplies actual recalculations.

## Report reference

- [Project Report Template Mockup](https://drive.google.com/file/d/1I6MbMMJTrPWSRw5XwNsV2O79pdxfOcFP/view)
- [Morro Bay AA intake example](https://drive.google.com/file/d/1DDOdzqVfhlARRbJuRtPqkuIUtsqvcC6_/view)

The report reproduces the mockup's section order, portrait format, blue headings/table headers, and confidentiality footer. Tables flow across pages rather than reproducing the mockup's clipped placeholders. References, component versions, open questions, and demo status are included. HTML/JSON exports are supported; direct PDF generation is not built in.

## Current limits and unresolved rules

- PDF intake uses text extraction and conservative labeled-field patterns. Narrative understanding, general table extraction, OCR, signed-approval recognition, and live LLM extraction are not implemented. Review all suggested facts.
- The Morro Bay document is a substation automation example. It is suitable for testing extraction, not validating pole-project forecasts. In-service dates are never substituted for IFC dates.
- The mockup says a 30-day schedule buffer; newer meeting notes say 45 days. The framework flags this conflict and reports the component's rule version. It does not choose an authoritative engineering rule.
- Milestone-hour allocation, stakeholder impacts, material rules, and confidence calibration require Group 2/PG&E guidance.
- Validations establish type, reference, input-identity, arithmetic consistency, and exact excerpt location. They do not prove that an engineering recommendation is correct or that a cited passage semantically supports every claim. Human review remains necessary.
- Single-user local app; no authentication, cloud deployment, portfolio view, automatic publishing, or external communication.

## Branch workflow

All prototype code belongs on `prototype`. Push with `git push origin prototype`; do not push or merge directly to `main`.
