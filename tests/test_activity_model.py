from __future__ import annotations

from datetime import date, time

import pytest

from garmin_tracker.activity_model import build_activity_row
from tests.fixtures import activity, indoor_cycling_activity, running_activity, strength_activity


def test_running_activity_computes_pace_and_speed() -> None:
    row = build_activity_row(running_activity())

    assert row.date == date(2026, 9, 20)
    assert row.start_time == time(9, 13, 31)
    assert row.sport_label == "Correr"
    assert row.distance_km == pytest.approx(10.01874)
    assert row.avg_speed_kmh == pytest.approx((10018.74 / 3100.489) * 3.6)
    assert row.avg_pace_min_per_km == pytest.approx(3100.489 / 60 / (10018.74 / 1000))
    assert row.avg_cadence == pytest.approx(166.8)
    assert row.vo2max == 59.0
    assert row.hr_zone_seconds[2] == pytest.approx(2579.6)


def test_indoor_cycling_has_no_pace_but_keeps_real_zero_speed() -> None:
    row = build_activity_row(indoor_cycling_activity())

    # distance/velocidad son 0.0 de verdad en el JSON -> se muestran, no se ocultan.
    assert row.distance_km == 0.0
    assert row.avg_speed_kmh == 0.0
    # el ritmo min/km no tiene sentido para ciclismo -> no se inventa.
    assert row.avg_pace_min_per_km is None
    assert row.sport_label == "Ciclismo indoor"


def test_missing_optional_fields_are_none_not_invented() -> None:
    row = build_activity_row(strength_activity())

    assert row.elevation_gain_m is None
    assert row.temp_min_c is None
    assert row.temp_max_c is None
    assert row.vo2max is None
    assert row.avg_power is None
    assert row.avg_cadence is None


def test_unknown_sport_key_falls_back_to_readable_label() -> None:
    activity = strength_activity()
    activity["activityType"] = {"typeKey": "stand_up_paddleboarding"}

    row = build_activity_row(activity)

    assert row.sport_label == "Stand up paddleboarding"


def test_treadmill_and_track_running_are_grouped_as_running() -> None:
    for sport in ("treadmill_running", "track_running", "running"):
        row = build_activity_row(activity(1, "2026-09-20 09:00:00", sport=sport, distance_m=5000, duration_s=1500))
        assert (row.sport_key, row.sport_label) == ("running", "Correr")
        assert row.avg_pace_min_per_km == 5.0  # el ritmo sigue calculándose
