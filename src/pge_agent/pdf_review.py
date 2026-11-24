"""Render the report once, then use the PDF's own link rectangles for editing."""
import base64
from datetime import datetime, timezone
from uuid import uuid4

import pymupdf
from playwright.sync_api import sync_playwright, Error

from .reporting import render_report

FIELD_URL = "https://report-field.invalid/"


def editable_fields(run):
    fields = {
        "risk_warning": run.forecast.critical_path_warning,
        "resource_overview": run.forecast.resource_overview,
        "permitting_summary": run.forecast.permitting_summary,
        "critical_path_summary": run.forecast.critical_path_summary,
    }
    fields.update({f"summary_{i}": claim.text for i, claim in enumerate(run.assessment.summary)})
    fields.update({f"step_{i}": step for i, step in enumerate(run.assessment.next_steps)})
    return fields


def revised_report(parent, edits):
    defaults = editable_fields(parent)
    if any(key not in defaults or not isinstance(value, str) or not value.strip()
           or len(value) > 5000 for key, value in edits.items()):
        raise ValueError("Each edited passage must contain 1–5,000 characters.")
    overrides = dict(parent.report_edits)
    for key, value in edits.items():
        if value.strip() == defaults[key]:
            overrides.pop(key, None)
        else:
            overrides[key] = value.strip()
    if overrides == parent.report_edits:
        raise ValueError("Change a passage before saving a revision.")
    return parent.model_copy(deep=True, update=dict(
        run_id=uuid4().hex, generated_at=datetime.now(timezone.utc),
        parent_run_id=parent.run_id, report_edits=overrides,
        review_status="draft", reviewer=None, reviewed_at=None))


def pdf_preview(run):
    fields = editable_fields(run) | run.report_edits
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="chrome")
        except Error:
            browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(render_report(run, editor_links=True))
            raw = page.pdf(prefer_css_page_size=True, print_background=True)
        finally:
            browser.close()
    pages = []
    with pymupdf.open(stream=raw, filetype="pdf") as doc:
        for page in doc:
            regions = []
            for link in page.get_links():
                url = link.get("uri", "")
                if url.startswith(FIELD_URL):
                    key = url[len(FIELD_URL):]
                    if key in fields:
                        box = link["from"]
                        regions.append(dict(key=key, x=box.x0/page.rect.width, y=box.y0/page.rect.height,
                                            w=box.width/page.rect.width, h=box.height/page.rect.height))
                    page.delete_link(link)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5))
            pages.append(dict(image=base64.b64encode(pix.tobytes("png")).decode(), regions=regions))
        pdf = doc.tobytes(garbage=4, deflate=True)
    return pdf, pages, fields
