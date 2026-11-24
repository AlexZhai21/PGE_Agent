import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from pge_agent.adapters import FixtureForecaster, FixtureRetriever, JsonForecaster
from pge_agent.demo import scenario
from pge_agent.intake import DocumentParser, FactExtractor, apply_fact, track_corrections
from pge_agent.models import DocumentPage, EvidenceItem, ParsedDocument, ProjectRecord
from pge_agent.reporting import render_report
from pge_agent.storage import RunStore
from pge_agent.workflow import compare_runs, generate


def demo_run(name="complete", **kwargs):
    sample=scenario(name)
    return generate(sample.project,retriever=FixtureRetriever(sample),
                    forecaster=FixtureForecaster(sample),allow_demo=True,**kwargs)


@pytest.mark.parametrize("name",["complete","missing","conflict"])
def test_demo_workflow(name):
    run=demo_run(name)
    assert not run.validation_errors
    assert run.demo
    html=render_report(run)
    assert "SYNTHETIC DEMONSTRATION" in html
    assert "{{" not in html
    assert "Material Schedule Table" in html
    if name=="missing":
        assert any(i.field=="construction_start" for i in run.issues)
        assert not run.forecast.materials
    if name=="conflict":
        assert any(i.kind=="conflict" for i in run.issues)
        assert run.project.construction_start==date(2027,5,1)


def test_corrections_invalidate_fixture_preserve_history(tmp_path):
    store=RunStore(tmp_path)
    old=demo_run()
    store.save(old)
    changed=old.project.model_copy(deep=True)
    changed.structures=11
    evidence=track_corrections(old.project,changed,[],"Corrected structure count")
    sample=scenario()
    new=generate(changed,evidence=evidence,retriever=FixtureRetriever(sample),
        forecaster=FixtureForecaster(sample),allow_demo=True,parent_run_id=old.run_id)
    store.save(new)
    assert new.forecast.status=="unavailable"
    assert new.forecast.hours.total is None
    assert new.review_status=="draft"
    assert store.get(old.run_id).forecast.hours.total==100
    assert any(c['field']=="project.structures" for c in compare_runs(old,new))
    assert evidence[-1].reason=="Corrected structure count"


def test_rejects_stale_or_inconsistent_response():
    sample=scenario()
    sample.forecast.hours.total=999
    sample.forecast.input_fingerprint="stale"
    run=generate(sample.project,retriever=FixtureRetriever(sample),
        forecaster=FixtureForecaster(sample),allow_demo=True)
    assert any("different inputs" in e for e in run.validation_errors)
    assert any("Calculation mismatch" in e for e in run.validation_errors)
    assert any("sum" in e for e in run.validation_errors)


def test_bad_citation_and_review_gate(tmp_path):
    sample=scenario()
    sample.forecast.risks[0].evidence_ids=["does-not-exist"]
    run=generate(sample.project,retriever=FixtureRetriever(sample),forecaster=FixtureForecaster(sample),allow_demo=True)
    store=RunStore(tmp_path)
    store.save(run)
    assert any("Unresolved evidence" in e for e in run.validation_errors)
    with pytest.raises(ValueError):
        store.review(run.run_id,"Engineer")


def test_saved_review_and_reload(tmp_path):
    store=RunStore(tmp_path)
    run=demo_run()
    store.save(run)
    store.review(run.run_id,"Engineer")
    assert RunStore(tmp_path).get(run.run_id).review_status=="reviewed"
    assert len(RunStore(tmp_path).list())==1


def test_conflict_cannot_be_marked_reviewed(tmp_path):
    store=RunStore(tmp_path)
    run=demo_run("conflict")
    store.save(run)
    with pytest.raises(ValueError,match="conflicts"):
        store.review(run.run_id,"Engineer")


def test_unknown_is_not_zero_or_no():
    project=ProjectRecord()
    assert project.structures is None
    assert project.outage_required is None
    with pytest.raises(ValidationError):
        ProjectRecord(structures=-1)
    assert ProjectRecord(structures=0).structures==0


def test_malformed_adapter_is_reported():
    run=generate(ProjectRecord(),forecaster=JsonForecaster('{"made_up": 10}'))
    assert run.forecast.status=="unavailable"
    assert run.validation_errors


def test_no_real_document_with_synthetic_forecast():
    doc=ParsedDocument(document_id="a",name="real.pdf",sha256="a",pages=[])
    with pytest.raises(ValueError,match="Synthetic"):
        demo_run(documents=[doc])


def test_basic_extraction_and_conflict_resolution():
    text="Project Name: Example 230 kV Project\nProject Number (T.Dot): T.0000001\nCore Team Members: TBD\nIn Service Date1: 6/1/2023\nOther site voltage 115 kV"
    doc=ParsedDocument(document_id="sample",name="example.pdf",sha256="sample",
                       pages=[DocumentPage(page=1,text=text)])
    evidence=FactExtractor().extract(doc)
    assert next(e for e in evidence if e.field=="voltage_kv").value==230
    assert next(e for e in evidence if e.field=="core_team").status=="missing"
    assert not any(e.field=="target_ifc" for e in evidence)
    project=ProjectRecord(voltage_kv=115)
    run=generate(project,evidence=evidence,documents=[doc])
    assert any(i.kind=="conflict" and i.field=="voltage_kv" for i in run.issues)
    fact=next(e for e in evidence if e.field=="voltage_kv")
    project,evidence=apply_fact(project,evidence,fact.evidence_id)
    assert project.voltage_kv==230
    assert not generate(project,evidence=evidence,documents=[doc]).validation_errors


def test_false_document_reference_detected():
    e=EvidenceItem(evidence_id="bad",field="project_name",original_text="fabricated",origin="document",page=1,document_id="missing")
    assert generate(ProjectRecord(),evidence=[e]).validation_errors


def test_html_escapes_user_input():
    run=generate(ProjectRecord(project_name='<script>alert(1)</script>'))
    html=render_report(run)
    assert '<script>' not in html
    assert '&lt;script&gt;' in html


def test_pdf_invalid_input():
    with pytest.raises(ValueError):
        DocumentParser().parse(b"not a PDF","bad.pdf")


def test_numeric_values_must_be_finite():
    with pytest.raises(ValidationError):
        ProjectRecord(voltage_kv=float('nan'))


def test_text_pdf_parsing_preserves_pages():
    from io import BytesIO
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer=PdfWriter()
    page=writer.add_blank_page(width=612,height=792)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 72 700 Td (Project Name: Synthetic 115 kV Project) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    writer.add_blank_page(width=612,height=792)
    raw=BytesIO();writer.write(raw)
    doc=DocumentParser().parse(raw.getvalue(),'synthetic.pdf')
    assert len(doc.pages)==2
    assert doc.pages[0].page==1
    assert 'Synthetic' in doc.pages[0].text
    assert any('Page 2' in w for w in doc.warnings)
    facts=FactExtractor().extract(doc)
    assert next(e for e in facts if e.field=='voltage_kv').value==115
