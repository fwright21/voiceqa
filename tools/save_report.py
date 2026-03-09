import sqlite3
import json
from pathlib import Path
from datetime import datetime
from langchain_core.tools import tool

# Database will be created in the project root
DB_PATH = Path(__file__).resolve().parent.parent / "voiceqa.db"


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the reports table if it doesn't exist."""
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT    NOT NULL,
            audio_name  TEXT    NOT NULL,
            expected    TEXT    NOT NULL,
            transcript  TEXT,
            wer         REAL,
            score       INTEGER,
            suggestions TEXT,
            full_report TEXT
        )
    """)
    conn.commit()
    conn.close()


@tool("save_report")
def save_report(
    audio_name:  str,
    expected:    str,
    transcript:  str,
    wer:         float,
    score:       int,
    suggestions: list,
    full_report: str,
) -> dict:
    """
    Save a completed VoiceQA report to the local SQLite database.

    Returns:
        { "report_id": int, "saved": True }
    """
    init_db()
    conn = _get_connection()
    cursor = conn.execute(
        """
        INSERT INTO reports
          (created_at, audio_name, expected, transcript, wer, score, suggestions, full_report)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.utcnow().isoformat(),
            audio_name,
            expected,
            transcript,
            wer,
            score,
            json.dumps(suggestions),
            full_report,
        ),
    )
    conn.commit()
    report_id = cursor.lastrowid
    conn.close()
    return {"report_id": report_id, "saved": True}