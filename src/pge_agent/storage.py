import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import AssessmentRun


class RunStore:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("PGE_AGENT_DATA_DIR", ".local"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "runs.sqlite3"
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, generated TEXT NOT NULL, name TEXT NOT NULL, payload TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.db)

    def save_document(self, data):
        digest = hashlib.sha256(data).hexdigest()
        folder = self.root / "documents"
        folder.mkdir(exist_ok=True)
        path = folder / f"{digest}.pdf"
        if not path.exists():
            path.write_bytes(data)
        return path

    def save(self, run: AssessmentRun):
        with self.connect() as con:
            con.execute("INSERT INTO runs VALUES (?, ?, ?, ?)",
                (run.run_id, run.generated_at.isoformat(),run.project.project_name,run.model_dump_json()))

    def get(self, run_id):
        with self.connect() as con:
            row = con.execute("SELECT payload FROM runs WHERE id=?",(run_id,)).fetchone()
        if not row:
            raise KeyError(run_id)
        return AssessmentRun.model_validate_json(row[0])

    def list(self):
        with self.connect() as con:
            return con.execute("SELECT id, generated, name FROM runs ORDER BY generated DESC").fetchall()

    def review(self, run_id, reviewer):
        run = self.get(run_id)
        if run.validation_errors:
            raise ValueError("Resolve validation errors before marking this revision reviewed.")
        if any(i.kind == "conflict" for i in run.issues):
            raise ValueError("Resolve input conflicts before marking this revision reviewed.")
        if not reviewer.strip():
            raise ValueError("Enter the reviewer's name.")
        run.review_status = "reviewed"
        run.reviewer = reviewer.strip()
        run.reviewed_at = datetime.now(timezone.utc)
        with self.connect() as con:
            con.execute("UPDATE runs SET payload=? WHERE id=?",(run.model_dump_json(),run_id))
        return run
