from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from garmin_tracker import storage
from garmin_tracker.sync import run_sync


class FakeClient:
    """Simula get_activities(start, limit) paginando sobre una lista fija
    de páginas, sin tocar la red ni Garmin de verdad."""

    def __init__(self, pages: list[list[dict[str, Any]]]) -> None:
        self._pages = pages

    def get_activities(self, start: int, limit: int) -> list[dict[str, Any]]:
        index = start // limit
        if index >= len(self._pages):
            return []
        return self._pages[index]


def _activity(activity_id: int, start_time: str) -> dict[str, Any]:
    return {
        "activityId": activity_id,
        "startTimeLocal": start_time,
        "activityType": {"typeKey": "running"},
    }


def _conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(storage.SCHEMA)
    return connection


def test_full_sync_first_run_downloads_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("garmin_tracker.sync.PAGE_SIZE", 2)
    pages = [
        [_activity(3, "2026-01-03 08:00:00"), _activity(2, "2026-01-02 08:00:00")],
        [_activity(1, "2026-01-01 08:00:00")],
    ]
    conn = _conn()

    result = run_sync(FakeClient(pages), conn, full=True)

    assert result.mode == "full"
    assert result.new_count == 3
    assert result.updated_count == 0
    assert storage.count_activities(conn) == 3


def test_first_run_without_full_flag_also_downloads_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("garmin_tracker.sync.PAGE_SIZE", 2)
    pages = [[_activity(1, "2026-01-01 08:00:00")]]
    conn = _conn()

    result = run_sync(FakeClient(pages), conn, full=False)

    assert "primera ejecución" in result.mode
    assert result.new_count == 1


def test_incremental_sync_stops_at_known_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("garmin_tracker.sync.PAGE_SIZE", 2)
    conn = _conn()
    storage.upsert_activity(conn, _activity(2, "2026-01-02 08:00:00"), "x")
    storage.upsert_activity(conn, _activity(1, "2026-01-01 08:00:00"), "x")
    conn.commit()

    pages = [
        [_activity(4, "2026-01-04 08:00:00"), _activity(3, "2026-01-03 08:00:00")],
        [_activity(2, "2026-01-02 08:00:00"), _activity(1, "2026-01-01 08:00:00")],
    ]

    result = run_sync(FakeClient(pages), conn, full=False)

    assert result.mode == "incremental"
    assert result.new_count == 2
    assert storage.count_activities(conn) == 4
    # No debería haber pedido la 2ª página completa: paró en cuanto vio el id 2.
    assert result.pages_fetched == 1


def test_desde_flag_stops_at_date_regardless_of_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    import datetime

    monkeypatch.setattr("garmin_tracker.sync.PAGE_SIZE", 2)
    conn = _conn()
    pages = [
        [_activity(3, "2026-01-03 08:00:00"), _activity(2, "2026-01-02 08:00:00")],
        [_activity(1, "2026-01-01 08:00:00")],
    ]

    result = run_sync(FakeClient(pages), conn, since=datetime.date(2026, 1, 2))

    assert result.mode == "desde"
    ids = {a["activityId"] for a in storage.all_raw_activities(conn)}
    assert ids == {3, 2}


def test_dry_run_does_not_write_to_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("garmin_tracker.sync.PAGE_SIZE", 2)
    conn = _conn()
    pages = [[_activity(1, "2026-01-01 08:00:00")]]

    result = run_sync(FakeClient(pages), conn, full=True, dry_run=True)

    assert result.new_count == 1
    assert storage.count_activities(conn) == 0


def test_full_resyncs_and_refreshes_already_cached_activities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("garmin_tracker.sync.PAGE_SIZE", 2)
    conn = _conn()
    storage.upsert_activity(conn, _activity(1, "2026-01-01 08:00:00"), "x")
    conn.commit()

    pages = [[_activity(1, "2026-01-01 08:00:00")]]

    result = run_sync(FakeClient(pages), conn, full=True)

    assert result.new_count == 0
    assert result.updated_count == 1
