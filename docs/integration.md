# Group 1 and 2 integration

All JSON records use `schema_version: "1.0"`; unknown properties are rejected. Dates use ISO `YYYY-MM-DD`. Missing values use JSON `null`, not zero or empty estimates.

## Input identity

Use `ProjectRecord` and `fingerprint` from `pge_agent.models`:

```python
project = ProjectRecord.model_validate_json(project_json)
identity = fingerprint(project)
```

Responses must set `input_fingerprint` to that identity. It covers the normalized full project record, including stakeholder inputs, proposed milestones, and engineer risks. The UI displays this identity; input changes invalidate old responses.

## HistoricalContext (Group 1)

Return `provider_version`, `status`, `comparables`, `evidence`, and `limitations`. Each comparable includes project ID, hours where known, similarity where available, a selection explanation, evidence IDs, and a basis of `actual`, `benchmark`, or `synthetic`. Evidence IDs must resolve. Missing historical outcomes are not inferred.

## ForecastResult (Group 2)

Return `provider_version`, `status`, `rule_version`, hours, milestones, phase breakdown, materials, risks, resources, permits, assumptions, calculations, and supporting evidence as available. `available` can contain partial results. `unavailable` must not contain numerical/date forecasts.

Keep requested milestone dates, internal targets, and external forecasts separate. Preserve the input dates when flagging infeasibility. Explicitly name the rule version and unresolved assumptions. The framework does not embed a 30-day or 45-day production scheduling rule.

Every quantitative/date result has a `numeric_refs` entry mapping its dotted output path to a calculation ID. Example paths: `hours.total`, `hours.phases.Scoping`, `milestones.0.internal_target`, `materials.0.lead_weeks`, and `schedule_buffer_days`. Each calculation includes a description, value, units, and evidence IDs where supplied. Dates use ISO strings. These checks verify consistency, not independent engineering correctness.

Evidence IDs must be unique across the input and both component responses. Use separate prefixes, or reference an existing ID without redeclaring it. Document-origin evidence must resolve to a loaded document's exact page excerpt. Reviewed user-origin evidence can describe other supplied sources. Do not label unverified external content as user-confirmed.

## Plug-in options

1. Implement the Python `HistoricalRetriever` and `ForecastEngine` protocols.
2. Supply JSON through the application's component-response upload controls.
3. CLI: `pge-agent run --project project.json --history history.json --forecast forecast.json`.

The synthetic examples in `examples/` provide a complete response pair. The CLI `demo` command is the explicit mode for running them. Normal real-project CLI runs reject demo component results.

## Report mapping

`ForecastResult` fields cover the mockup's schedule calculator, phase table, engineering hours, resources, materials, permits, risks, roadblocks, and next steps. Project fields supply the snapshot. `Assessment` supplies the summary and limitations. Missing sections remain visible as unavailable. The report appends source and calculation detail inside Assumptions & Caveats rather than hiding unsupported outputs.

Future model-generated summaries require additional semantic/claim validation. The current template writer uses only supplied totals and reference-backed statements.
