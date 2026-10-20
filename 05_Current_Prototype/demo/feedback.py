"""Local append-only reviewer feedback. Feedback is never used as model input."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "feedback.sqlite3"
DECISIONS = frozenset({"confirmed", "false_alarm", "needs_review"})


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("""CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        case_id TEXT NOT NULL,
        decision TEXT NOT NULL CHECK(decision IN ('confirmed', 'false_alarm', 'needs_review')),
        note TEXT NOT NULL,
        context_json TEXT NOT NULL
    )""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS feedback_no_update
        BEFORE UPDATE ON feedback BEGIN SELECT RAISE(ABORT, 'feedback is append-only'); END""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS feedback_no_delete
        BEFORE DELETE ON feedback BEGIN SELECT RAISE(ABORT, 'feedback is append-only'); END""")
    return connection


def save_feedback(case_id: str, decision: str, note: str, context: dict | None = None) -> None:
    if not isinstance(case_id, str) or not case_id.strip() or len(case_id) > 200:
        raise ValueError("A valid case ID is required")
    if decision not in DECISIONS:
        raise ValueError("Invalid feedback decision")
    if not isinstance(note, str) or len(note) > 4000:
        raise ValueError("Feedback note is too long")
    if context is not None and not isinstance(context, dict):
        raise ValueError("Feedback context must be a dictionary")
    context_json = json.dumps(context or {}, sort_keys=True, ensure_ascii=False)
    if len(context_json) > 8000:
        raise ValueError("Feedback context is too large")
    with closing(_connect()) as connection:
        with connection:
            connection.execute(
                "INSERT INTO feedback (created_at, case_id, decision, note, context_json) VALUES (?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), case_id.strip(), decision, note.strip(), context_json),
            )


def load_feedback() -> list[dict]:
    if not DB_PATH.exists():
        return []
    with closing(_connect()) as connection:
        rows = connection.execute("SELECT id, created_at, case_id, decision, note, context_json FROM feedback ORDER BY id").fetchall()
    return [{**dict(row), "context": json.loads(row["context_json"])} for row in rows]
