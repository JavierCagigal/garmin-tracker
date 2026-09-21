"""Caché SQLite de actividades: guarda el JSON crudo completo tal cual lo
devuelve Garmin, sin filtrar ni recortar campos, para no tener que volver a
descargar nada el día que haga falta una métrica nueva.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
    activity_id INTEGER PRIMARY KEY,
    start_time_local TEXT NOT NULL,
    sport_type TEXT,
    raw_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activities_start_time ON activities (start_time_local);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def existing_activity_ids(conn: sqlite3.Connection) -> set[int]:
    rows = conn.execute("SELECT activity_id FROM activities").fetchall()
    return {row[0] for row in rows}


def latest_start_time(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(start_time_local) FROM activities").fetchone()
    return row[0] if row else None


def upsert_activity(conn: sqlite3.Connection, activity: dict[str, Any], fetched_at: str) -> None:
    activity_id = activity["activityId"]
    start_time_local = activity.get("startTimeLocal", "")
    sport_type = (activity.get("activityType") or {}).get("typeKey")
    conn.execute(
        """
        INSERT INTO activities (activity_id, start_time_local, sport_type, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(activity_id) DO UPDATE SET
            start_time_local = excluded.start_time_local,
            sport_type = excluded.sport_type,
            raw_json = excluded.raw_json,
            fetched_at = excluded.fetched_at
        """,
        (activity_id, start_time_local, sport_type, json.dumps(activity, ensure_ascii=False), fetched_at),
    )


def count_activities(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]


def all_raw_activities(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Todas las actividades cacheadas, más reciente primero, como dicts
    (el JSON crudo íntegro que devolvió Garmin en su momento)."""
    rows = conn.execute(
        "SELECT raw_json FROM activities ORDER BY start_time_local DESC"
    ).fetchall()
    return [json.loads(row[0]) for row in rows]
