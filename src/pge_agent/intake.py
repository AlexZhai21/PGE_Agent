"""Conservative labeled-field suggestions; documents are data, never instructions."""
import hashlib
import re
from datetime import datetime
from io import BytesIO
from uuid import uuid4

from pypdf import PdfReader

from .models import DocumentPage, EvidenceItem, ParsedDocument, ProjectRecord


class DocumentParser:
    def parse(self, data: bytes, name: str) -> ParsedDocument:
        if len(data) > 20 * 1024 * 1024:
            raise ValueError("PDF exceeds the 20 MB local intake limit.")
        if not data.startswith(b"%PDF-"):
            raise ValueError("Select a PDF document.")
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs require an unlocked copy.")
            if len(reader.pages) > 100:
                raise ValueError("PDF exceeds the 100-page intake limit.")
            pages, warnings = [], []
            for i, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                pages.append(DocumentPage(page=i, text=text))
                if len(text.strip()) < 250:
                    warnings.append(f"Page {i}: little extractable text; review images or enter information manually.")
            digest = hashlib.sha256(data).hexdigest()
            return ParsedDocument(document_id=digest, sha256=digest, name=name,
                                  pages=pages, warnings=warnings)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Could not parse PDF; use manual entry or an unlocked PDF.") from exc


class FactExtractor:
    version = "labeled-fields-1"
    patterns = {
        "project_name": r"Project Name:\s*([^\n\r]+)",
        "project_number": r"Project Number\s*\(T\.?Dot\):\s*(T\.\d+)",
        "project_manager": r"Project Manager:\s*(.*?)(?=Core Team|\n|\r)",
        "core_team": r"Core Team Members:\s*([^\n\r]+)",
        "project_start": r"Project Start Date:\s*(\d{1,2}/\d{1,2}/\d{4})",
        "project_completion": r"Project Completion Date:\s*(\d{1,2}/\d{1,2}/\d{4})",
        "in_service_date": r"In Service Date\s*\d?\s*:\s*(\d{1,2}/\d{1,2}/\d{4})",
    }

    def extract(self, document: ParsedDocument) -> list[EvidenceItem]:
        facts = []
        for page in document.pages:
            for field, pattern in self.patterns.items():
                for match in re.finditer(pattern, page.text, re.I):
                    value = match.group(1).strip()
                    missing = value.upper() in {"TBD", "TO BE DETERMINED", "UNKNOWN", ""}
                    if field in {"project_start", "project_completion", "in_service_date"}:
                        try:
                            value = datetime.strptime(value, "%m/%d/%Y").date().isoformat()
                        except ValueError:
                            continue
                    facts.append(self._fact(document, page.page, field, None if missing else value,
                                            match.group(0), "missing" if missing else "proposed"))
                    # Voltage must come from the named project, not incidental site voltage.
                    if field == "project_name":
                        voltage = re.search(r"(\d+)\s*kV", value, re.I)
                        if voltage:
                            facts.append(self._fact(document, page.page, "voltage_kv",
                                                    float(voltage.group(1)), match.group(0), "proposed", "kV"))
        return facts

    @staticmethod
    def _fact(doc, page, field, value, text, status, units=None):
        key = hashlib.sha256(f"{doc.document_id}:{page}:{field}:{text}".encode()).hexdigest()[:24]
        return EvidenceItem(evidence_id=key, field=field, value=value, units=units,
                            original_text=text, origin="document", document_id=doc.document_id,
                            page=page, status=status)


def apply_fact(project: ProjectRecord, evidence: list[EvidenceItem], fact_id: str):
    copied = [e.model_copy(deep=True) for e in evidence]
    fact = next(e for e in copied if e.evidence_id == fact_id)
    if fact.value is None:
        raise ValueError("Missing facts cannot populate a field.")
    values = project.model_dump()
    values[fact.field] = fact.value
    result = ProjectRecord.model_validate(values)
    for e in copied:
        if e.field == fact.field and e.status == "confirmed":
            e.status = "superseded"
    fact.status = "confirmed"
    return result, copied


def track_corrections(before: ProjectRecord, after: ProjectRecord,
                      evidence: list[EvidenceItem], reason: str) -> list[EvidenceItem]:
    result = [e.model_copy(deep=True) for e in evidence]
    old, new = before.model_dump(mode="json"), after.model_dump(mode="json")
    for field, value in new.items():
        if old.get(field) == value:
            continue
        for e in result:
            if e.field == field and e.status in {"confirmed", "proposed"}:
                e.status = "superseded"
        result.append(EvidenceItem(evidence_id=uuid4().hex, field=field,
                    value=value if isinstance(value, (str, int, float, bool)) else None,
                    original_text=str(value), origin="user", status="confirmed",
                    reason=reason.strip() or "Entered by engineer"))
    return result
