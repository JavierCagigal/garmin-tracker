from __future__ import annotations

from datetime import date

import pytest

from garmin_tracker.activity_model import build_activity_row
from garmin_tracker.aggregates import TOTAL_SPORT_KEY, aggregate_by_week, iso_week_key, moving_average
from tests.fixtures import activity


def test_iso_week_key_groups_monday_to_sunday_together() -> None:
    assert iso_week_key(date(2026, 9, 14)) == iso_week_key(date(2026, 9, 18))
    assert iso_week_key(date(2026, 9, 14)) != iso_week_key(date(2026, 9, 21))


def test_weighted_pace_is_distance_weighted_not_mean_of_means() -> None:
    # Sesión A: 10 km en 60 min (6:00 min/km). Sesión B: 2 km en 6 min (3:00 min/km).
    # Media simple de ritmos = 4:30 min/km. Media ponderada por distancia:
    # (60 + 6) min / (10 + 2) km = 5.5 min/km.
    rows = [
        build_activity_row(activity(1, "2026-09-14 08:00:00", sport="running", distance_m=10000, duration_s=3600)),
        build_activity_row(activity(2, "2026-09-15 08:00:00", sport="running", distance_m=2000, duration_s=360)),
    ]
    total = next(w for w in aggregate_by_week(rows) if w.sport_key == TOTAL_SPORT_KEY)
    assert total.weighted_avg_pace_min_per_km == pytest.approx(5.5, abs=0.01)


def test_weighted_pace_ignores_non_running_sports() -> None:
    rows = [
        build_activity_row(activity(1, "2026-09-14 08:00:00", sport="running", distance_m=5000, duration_s=1500)),
        build_activity_row(activity(2, "2026-09-15 08:00:00", sport="cycling", distance_m=30000, duration_s=3600)),
    ]
    total = next(w for w in aggregate_by_week(rows) if w.sport_key == TOTAL_SPORT_KEY)
    assert total.weighted_avg_pace_min_per_km == pytest.approx(5.0, abs=0.01)


def test_weighted_hr_is_time_weighted() -> None:
    # 60 min a 140 lpm + 30 min a 170 lpm -> (60*140 + 30*170) / 90 = 150
    rows = [
        build_activity_row(activity(1, "2026-09-14 08:00:00", duration_s=3600, avg_hr=140.0)),
        build_activity_row(activity(2, "2026-09-15 08:00:00", duration_s=1800, avg_hr=170.0)),
    ]
    total = next(w for w in aggregate_by_week(rows) if w.sport_key == TOTAL_SPORT_KEY)
    assert total.weighted_avg_hr == pytest.approx(150.0, abs=0.01)


def test_produces_total_and_per_sport_rows() -> None:
    rows = [
        build_activity_row(activity(1, "2026-09-14 08:00:00", sport="running")),
        build_activity_row(
            activity(2, "2026-09-15 08:00:00", sport="strength_training", distance_m=0, hr_zones=(600.0, 300.0, 0.0, 0.0, 0.0))
        ),
    ]
    weekly = aggregate_by_week(rows)
    sport_keys = {w.sport_key for w in weekly}
    assert {TOTAL_SPORT_KEY, "running", "strength_training"} <= sport_keys
    total = next(w for w in weekly if w.sport_key == TOTAL_SPORT_KEY)
    assert total.sessions == 2


def test_zone_split_easy_vs_intense() -> None:
    # zonas 1-2 = 20 min (suave), zonas 3-5 = 10 min (intenso) -> 66.7% / 33.3%
    rows = [build_activity_row(activity(1, "2026-09-14 08:00:00", hr_zones=(600.0, 600.0, 300.0, 300.0, 0.0)))]
    total = next(w for w in aggregate_by_week(rows) if w.sport_key == TOTAL_SPORT_KEY)
    assert total.pct_time_easy == pytest.approx(66.67, abs=0.1)
    assert total.pct_time_intense == pytest.approx(33.33, abs=0.1)


def test_moving_average_uses_partial_window_at_the_start() -> None:
    assert moving_average([10.0], window=4) == [10.0]
    assert moving_average([10.0, 20.0], window=4) == [10.0, 15.0]


def test_moving_average_uses_full_trailing_window_once_available() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 100.0]
    result = moving_average(values, window=4)
    # 5º punto: media de los 4 últimos (20,30,40,100) = 47.5
    assert result[-1] == pytest.approx(47.5)


def test_training_load_sums_across_week() -> None:
    rows = [
        build_activity_row(activity(1, "2026-09-14 08:00:00", hr_zones=(600.0, 0.0, 0.0, 0.0, 0.0))),  # 10 min z1 = 10
        build_activity_row(activity(2, "2026-09-15 08:00:00", hr_zones=(0.0, 0.0, 600.0, 0.0, 0.0))),  # 10 min z3 = 30
    ]
    total = next(w for w in aggregate_by_week(rows) if w.sport_key == TOTAL_SPORT_KEY)
    assert total.training_load == pytest.approx(40.0)
