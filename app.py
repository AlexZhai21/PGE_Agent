"""Launch with: streamlit run app.py --server.address 127.0.0.1"""
import json
from datetime import date

import streamlit as st
from pydantic import ValidationError

from pge_agent.adapters import (FixtureForecaster, FixtureRetriever, JsonForecaster, JsonRetriever)
from pge_agent.demo import STAKEHOLDERS, scenario
from pge_agent.intake import DocumentParser, FactExtractor, autofill_candidates, apply_fact, track_corrections
from pge_agent.models import ProjectRecord, fingerprint
from pge_agent.reporting import render_report
from pge_agent.storage import RunStore
from pge_agent.workflow import compare_runs, generate

st.set_page_config(page_title="T-Line Forecast Prototype",page_icon="📋",layout="wide")
store = RunStore()


def reset(project=None, demo_name=None):
    st.session_state.project = project or ProjectRecord(stakeholders={s:None for s in STAKEHOLDERS})
    st.session_state.evidence = []
    st.session_state.documents = []
    st.session_state.parent = None
    st.session_state.current = None
    st.session_state.demo_name = demo_name
    st.session_state.editor_version = st.session_state.get("editor_version",0)+1


if "project" not in st.session_state:
    reset()

st.title("T-Line Project Forecast")
st.caption("DSS Group 3 prototype · Local intake, integration, and engineer review")
with st.sidebar:
    st.header("Workspace")
    if st.button("New project"):
        reset()
        st.rerun()
    selected_demo = st.selectbox("Synthetic example",["complete","missing","conflict"])
    if st.button("Load demonstration"):
        reset(scenario(selected_demo).project,selected_demo)
        st.rerun()
    saved = store.list()
    if saved:
        selection = st.selectbox("Saved runs",[r[0] for r in saved],
            format_func=lambda rid: next(f"{r[2] or 'Unnamed'} · {r[1][:16]} · {r[0][:8]}" for r in saved if r[0]==rid))
        if st.button("Open saved run"):
            run = store.get(selection)
            reset(run.project)
            st.session_state.evidence = [e for e in run.evidence if e.origin != "synthetic" and e not in run.history.evidence and e not in run.forecast.evidence]
            st.session_state.documents = run.documents
            st.session_state.parent = run.run_id
            st.session_state.current = run.run_id
            for name in ["complete","missing","conflict"]:
                if run.demo and fingerprint(run.project)==fingerprint(scenario(name).project):
                    st.session_state.demo_name=name
            st.rerun()
    st.caption("Saved locally. No model or cloud service is called.")

if st.session_state.demo_name:
    st.warning("Synthetic demonstration mode. Example numbers and dates are not PG&E estimates. Editing the example invalidates its static fixture results.")

tabs = st.tabs(["1 · Intake","2 · Review inputs","3 · Generate report","4 · Revisions"])
with tabs[0]:
    st.subheader("Authorization document")
    uploaded = st.file_uploader("Optional AA PDF (up to 20 MB / 100 pages)",type=["pdf"], key=f"pdf-{st.session_state.editor_version}")
    if st.button("Read uploaded PDF",disabled=uploaded is None):
        try:
            data=uploaded.getvalue()
            doc=DocumentParser().parse(data,uploaded.name)
            if doc.document_id not in [d.document_id for d in st.session_state.documents]:
                if st.session_state.demo_name:
                    reset()
                store.save_document(data)
                st.session_state.documents.append(doc)
                st.session_state.evidence.extend(FactExtractor().extract(doc))
                st.session_state.current=None
            st.success("PDF read. Review and accept suggestions in the next tab.")
        except ValueError as exc:
            st.error(str(exc))
    for doc in st.session_state.documents:
        with st.expander(doc.name):
            for warning in doc.warnings:
                st.warning(warning)
            for page in doc.pages:
                st.markdown(f"**Page {page.page}**")
                st.text(page.text or "No extractable text")

with tabs[1]:
    st.subheader("Source suggestions")
    candidates = autofill_candidates(st.session_state.project, st.session_state.evidence)
    if candidates and st.button(f"Autofill {len(candidates)} suggested fields", key="autofill"):
        for candidate in candidates:
            st.session_state.project, st.session_state.evidence = apply_fact(
                st.session_state.project, st.session_state.evidence, candidate.evidence_id
            )
        st.session_state.editor_version += 1
        st.session_state.current = None
        st.rerun()
    for e in st.session_state.evidence:
        if e.origin != "document" or e.status == "superseded":
            continue
        with st.expander(f"{e.field}: {e.value if e.value is not None else 'Missing'} · page {e.page} · {e.status}"):
            st.text(e.original_text)
            if e.value is not None and e.status == "proposed" and st.button("Use this value",key=e.evidence_id):
                st.session_state.project,st.session_state.evidence=apply_fact(st.session_state.project,st.session_state.evidence,e.evidence_id)
                st.session_state.editor_version+=1
                st.session_state.current=None
                st.rerun()
    p=st.session_state.project
    version=st.session_state.editor_version
    st.subheader("Project details")
    st.caption("Blank numeric fields and dates mean unknown. The editor never substitutes zero.")
    with st.form(f"inputs-{version}"):
        values=p.model_dump(mode="json")
        a,b=st.columns(2)
        fields=["project_name","project_number","requestor","project_type","voltage_kv","structures","line_miles",
                "terrain","hftd_tier","permitting","project_manager","core_team","target_ifc","construction_start",
                "project_start","in_service_date","project_completion"]
        edited={}
        for i,field in enumerate(fields):
            with a if i%2==0 else b:
                edited[field]=st.text_input(field.replace('_',' ').title(),value="" if values[field] is None else str(values[field]),key=f"{version}-{field}")
        for field in ["outage_required","contracted_engineering"]:
            choice=st.selectbox(field.replace('_',' ').title(),["Unknown","Yes","No"],index={None:0,True:1,False:2}[values[field]],key=f"{version}-{field}")
            edited[field]={"Unknown":None,"Yes":True,"No":False}[choice]
        st.markdown("**Stakeholder involvement**")
        stakeholder_values={}
        for name in dict.fromkeys(STAKEHOLDERS+list(values["stakeholders"])):
            choice=st.selectbox(name,["Unknown","Yes","No"],index={None:0,True:1,False:2}[values["stakeholders"].get(name)],key=f"{version}-{name}")
            stakeholder_values[name]={"Unknown":None,"Yes":True,"No":False}[choice]
        scope=st.text_area("Scope",p.scope,key=f"scope-{version}")
        materials=st.text_area("Materials (JSON list)",json.dumps(values["materials"],indent=2),help='Example: [{"name":"Conductor","lead_weeks":null,"need_by":null}]')
        milestones=st.text_area("Engineer-proposed milestone dates (JSON object)",json.dumps(values["proposed_milestones"],indent=2),help='Example: {"30% Design Complete":"2027-03-01"}')
        risks=st.text_area("Engineer-added risks (one per line)","\n".join(p.engineer_risks))
        reason=st.text_input("Reason for changes","Engineer input review")
        submitted=st.form_submit_button("Save reviewed inputs")
    if submitted:
        try:
            for field in fields:
                val=edited[field].strip()
                edited[field]=val if val else ("" if field in ["project_name","project_number","requestor","project_type"] else None)
            updated=ProjectRecord.model_validate({**values,**edited,"stakeholders":stakeholder_values,
                "scope":scope,"materials":json.loads(materials),"proposed_milestones":json.loads(milestones),
                "engineer_risks":[r.strip() for r in risks.splitlines() if r.strip()]})
            st.session_state.evidence=track_corrections(p,updated,st.session_state.evidence,reason)
            st.session_state.project=updated
            st.session_state.current=None
            st.success("Inputs saved. Generate a new report to apply changes.")
        except (ValueError,ValidationError) as exc:
            st.error(f"Could not save inputs: {exc}")

with tabs[2]:
    st.subheader("Component integration")
    mode=st.radio("Results source",["Default / demonstration adapters","Group 1 and 2 JSON responses"],horizontal=True)
    history_upload=forecast_upload=None
    if mode=="Group 1 and 2 JSON responses":
        history_upload=st.file_uploader("Group 1 historical context JSON",type=["json"],key="history-json")
        forecast_upload=st.file_uploader("Group 2 forecast JSON",type=["json"],key="forecast-json")
    st.caption(f"Current input fingerprint: {fingerprint(st.session_state.project)}")
    st.download_button("Download component input JSON",st.session_state.project.model_dump_json(indent=2),"project.json","application/json")
    if st.button("Generate and save report",type="primary"):
        try:
            retriever=forecaster=None
            if mode=="Group 1 and 2 JSON responses":
                retriever=JsonRetriever(history_upload.getvalue().decode()) if history_upload else None
                forecaster=JsonForecaster(forecast_upload.getvalue().decode()) if forecast_upload else None
            elif st.session_state.demo_name:
                sample=scenario(st.session_state.demo_name)
                retriever,forecaster=FixtureRetriever(sample),FixtureForecaster(sample)
            run=generate(st.session_state.project,evidence=st.session_state.evidence,
                documents=st.session_state.documents,retriever=retriever,forecaster=forecaster,
                parent_run_id=st.session_state.parent,allow_demo=bool(st.session_state.demo_name))
            store.save(run)
            st.session_state.current=run.run_id
            st.session_state.parent=run.run_id
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if st.session_state.current:
        run=store.get(st.session_state.current)
        st.caption(f"Run {run.run_id} · {run.review_status}")
        for error in run.validation_errors:
            st.error(error)
        if run.issues:
            st.dataframe([i.model_dump(exclude={"schema_version"}) for i in run.issues],hide_index=True)
        html=render_report(run)
        st.download_button("Download formatted report",html,f"forecast-{run.run_id[:8]}.html","text/html")
        st.download_button("Download assessment JSON",run.model_dump_json(indent=2),f"assessment-{run.run_id[:8]}.json","application/json")
        st.caption("Open the HTML report in your browser and print to PDF. Use Letter paper, enable background graphics, and disable browser-added headers and footers.")
        import streamlit.components.v1 as components
        components.html(html,height=850,scrolling=True)
        reviewer=st.text_input("Reviewer name")
        if st.button("Mark this revision reviewed",disabled=bool(run.validation_errors)):
            try:
                store.review(run.run_id,reviewer)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

with tabs[3]:
    st.subheader("Revision history")
    st.write("Open a saved run from the sidebar, change its inputs, and generate a new report. Each rerun retains its parent revision.")
    if st.session_state.current:
        run=store.get(st.session_state.current)
        if run.parent_run_id:
            old=store.get(run.parent_run_id)
            st.caption(f"Comparing {old.run_id[:8]} → {run.run_id[:8]}")
            changes=compare_runs(old,run)
            st.dataframe([{**c,"before":json.dumps(c['before']),"after":json.dumps(c['after'])} for c in changes],hide_index=True) if changes else st.info("No input or result changes.")
        else:
            st.info("This is the first revision.")
