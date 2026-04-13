import sqlite3
import json
from pathlib import Path
from datetime import datetime
from langchain_core.tools import tool

DB_PATH = Path(__file__).resolve().parent.parent / "voiceqa.db"

# Full target schema — all columns voice_qa v2 expects
_SCHEMA = """
    CREATE TABLE IF NOT EXISTS reports (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at             TEXT    NOT NULL,
        audio_name             TEXT    NOT NULL,
        expected               TEXT    NOT NULL,
        transcript             TEXT,
        transcript_confidence  TEXT,
        wer                    REAL,
        score                  INTEGER,
        verdict                TEXT,
        failures               TEXT,
        prosody_score          REAL,
        f0_mean                REAL,
        jitter                 REAL,
        shimmer                REAL,
        hnr                    REAL,
        mos_score              REAL,
        entity_fidelity_score  REAL,
        name_fidelity_score    REAL,
        faithfulness_score     REAL,
        violations             TEXT,
        suggestions            TEXT,
        full_report            TEXT
    )
"""

# Columns added in v2 — migrate_db() will add any that are missing
_V2_COLUMNS = [
    ("transcript_confidence", "TEXT"),
    ("verdict",               "TEXT"),
    ("failures",              "TEXT"),
    ("prosody_score",         "REAL"),
    ("f0_mean",               "REAL"),
    ("jitter",                "REAL"),
    ("shimmer",               "REAL"),
    ("hnr",                   "REAL"),
    ("mos_score",             "REAL"),
    ("entity_fidelity_score", "REAL"),
    ("name_fidelity_score",   "REAL"),
    ("faithfulness_score",    "REAL"),
    ("violations",            "TEXT"),
]


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def migrate_db():
    """
    Create the reports table if it doesn't exist, then add any missing v2 columns.
    Safe to call on every startup — idempotent.
    """
    conn = _get_connection()
    conn.execute(_SCHEMA)
    conn.commit()

    # Check which columns already exist
    cursor = conn.execute("PRAGMA table_info(reports)")
    existing = {row["name"] for row in cursor.fetchall()}

    for col_name, col_type in _V2_COLUMNS:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE reports ADD COLUMN {col_name} {col_type}")
            print(f"[migrate_db] Added column: {col_name}")

    conn.commit()
    conn.close()


@tool("save_report")
def save_report(
    audio_name:            str,
    expected:              str,
    transcript:            str,
    wer:                   float,
    score:                 int,
    verdict:               str,
    failures:              list,
    suggestions:           list,
    full_report:           str,
    transcript_confidence: str   = "ok",
    prosody_score:         float = None,
    f0_mean:               float = None,
    jitter:                float = None,
    shimmer:               float = None,
    hnr:                   float = None,
    mos_score:             float = None,
    entity_fidelity_score: float = None,
    name_fidelity_score:   float = None,
    faithfulness_score:    float = None,
    violations:            list  = None,
) -> dict:
    """
    Save a completed VoiceQA v2 report to the local SQLite database.

    Returns:
        { "report_id": int, "saved": True }
    """
    migrate_db()
    conn = _get_connection()
    cursor = conn.execute(
        """
        INSERT INTO reports (
            created_at, audio_name, expected, transcript,
            transcript_confidence, wer, score, verdict, failures,
            prosody_score, f0_mean, jitter, shimmer, hnr,
            mos_score, entity_fidelity_score, name_fidelity_score, faithfulness_score, violations,
            suggestions, full_report
        ) VALUES (
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?
        )
        """,
        (
            datetime.utcnow().isoformat(),
            audio_name,
            expected,
            transcript,
            transcript_confidence,
            wer,
            score,
            verdict,
            json.dumps(failures or []),
            prosody_score,
            f0_mean,
            jitter,
            shimmer,
            hnr,
            mos_score,
            entity_fidelity_score,
            name_fidelity_score,
            faithfulness_score,
            json.dumps(violations or []),
            json.dumps(suggestions or []),
            full_report,
        ),
    )
    conn.commit()
    report_id = cursor.lastrowid
    conn.close()
    return {"report_id": report_id, "saved": True}
