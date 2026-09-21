from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from garmin_tracker import storage


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(storage.SCHEMA)
    yield connection
    connection.close()


def _activity(activity_id: int, start_time: str, sport: str = "running") -> dict[str, Any]:
    return {
        "activityId": activity_id,
        "startTimeLocal": start_time,
        "activityType": {"typeKey": sport},
        "distance": 5000.0,
    }


def test_upsert_new_activity_is_stored(conn: sqlite3.Connection) -> None:
    storage.upsert_activity(conn, _activity(1, "2026-01-01 08:00:00"), "2026-01-01T08:05:00Z")
    conn.commit()

    assert storage.count_activities(conn) == 1
    assert storage.existing_activity_ids(conn) == {1}


def test_upsert_existing_activity_overwrites_raw_json(conn: sqlite3.Connection) -> None:
    storage.upsert_activity(conn, _activity(1, "2026-01-01 08:00:00"), "2026-01-01T08:05:00Z")
    updated = _activity(1, "2026-01-01 08:00:00")
    updated["distance"] = 5200.0

    storage.upsert_activity(conn, updated, "2026-01-02T08:05:00Z")
    conn.commit()

    assert storage.count_activities(conn) == 1
    [raw] = storage.all_raw_activities(conn)
    assert raw["distance"] == 5200.0


def test_latest_start_time_returns_max(conn: sqlite3.Connection) -> None:
    storage.upsert_activity(conn, _activity(1, "2026-01-01 08:00:00"), "x")
    storage.upsert_activity(conn, _activity(2, "2026-01-05 08:00:00"), "x")
    conn.commit()

    assert storage.latest_start_time(conn) == "2026-01-05 08:00:00"


def test_latest_start_time_empty_cache_is_none(conn: sqlite3.Connection) -> None:
    assert storage.latest_start_time(conn) is None


def test_all_raw_activities_orders_most_recent_first(conn: sqlite3.Connection) -> None:
    storage.upsert_activity(conn, _activity(1, "2026-01-01 08:00:00"), "x")
    storage.upsert_activity(conn, _activity(2, "2026-01-05 08:00:00"), "x")
    conn.commit()

    ids = [a["activityId"] for a in storage.all_raw_activities(conn)]
    assert ids == [2, 1]
