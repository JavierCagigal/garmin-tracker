from __future__ import annotations

from datetime import date, timedelta

import pytest

from garmin_tracker.activity_model import build_activity_row
from garmin_tracker.aggregates import TOTAL_SPORT_KEY, aggregate_by_week
from garmin_tracker.progression import (
    acwr_series,
    compute_weekly_deltas,
    continuous_weekly_totals,
    current_personal_bests,
    efficiency_factor_deltas,
    efficiency_factor_series,
    personal_best_history,
)
from tests.fixtures import activity


def _monday_on_or_before(d: date) -> date:
    return d - timedelta(days=d.weekday())


def test_continuous_weekly_totals_fills_rest_weeks_with_zero() -> None:
    start = _monday_on_or_before(date(2026, 6, 1))
    later = start + timedelta(days=21)  # 3 semanas después: deja 2 semanas de hueco

    rows = [
        build_activity_row(activity(1, start.isoformat() + " 08:00:00")),
        build_activity_row(activity(2, later.isoformat() + " 08:00:00")),
    ]
    weekly_totals = continuous_weekly_totals(rows)

    assert len(weekly_totals) == 4
    middle_weeks = weekly_totals[1:3]
    assert all(w.sessions == 0 for w in middle_weeks)
    assert all(w.training_load == 0.0 for w in middle_weeks)


def test_compute_weekly_deltas_vs_previous_week() -> None:
    start = _monday_on_or_before(date(2026, 6, 1))
    week2_day = start + timedelta(days=7)

    rows = [
        build_activity_row(activity(1, start.isoformat() + " 08:00:00", distance_m=5000, duration_s=1500)),
        build_activity_row(activity(2, week2_day.isoformat() + " 08:00:00", distance_m=10000, duration_s=3000)),
    ]
    deltas = compute_weekly_deltas(continuous_weekly_totals(rows))
    week2_delta = deltas[-1]

    assert week2_delta.volume_km.value == pytest.approx(10.0)
    assert week2_delta.volume_km.delta_vs_prev == pytest.approx(5.0)
    assert week2_delta.volume_km.pct_vs_prev == pytest.approx(100.0)
    assert week2_delta.comparable is False  # solo 1 sesión esa semana


def test_compute_weekly_deltas_ma4_needs_four_prior_weeks() -> None:
    start = _monday_on_or_before(date(2026, 6, 1))
    rows = [build_activity_row(activity(1, start.isoformat() + " 08:00:00"))]
    deltas = compute_weekly_deltas(continuous_weekly_totals(rows))

    assert deltas[0].volume_km.delta_vs_ma4 is None  # no hay ni una semana previa completa


def test_acwr_flags_spike_as_alto() -> None:
    start = _monday_on_or_before(date(2026, 6, 1))
    rows = []
    for i in range(28):
        day = start + timedelta(days=i)
        load = 20.0 if i >= 21 else 10.0
        rows.append(
            build_activity_row(
                activity(100 + i, day.isoformat() + " 08:00:00", hr_zones=(load * 60, 0.0, 0.0, 0.0, 0.0))
            )
        )

    weekly_totals = continuous_weekly_totals(rows)
    last = acwr_series(rows, weekly_totals)[-1]

    expected_chronic = (21 * 10 + 7 * 20) / 28
    assert last.as_of == start + timedelta(days=27)
    assert last.acute_7d_avg == pytest.approx(20.0)
    assert last.chronic_28d_avg == pytest.approx(expected_chronic)
    assert last.ratio == pytest.approx(20.0 / expected_chronic)
    assert last.status == "alto"


def test_acwr_flags_drop_as_bajo() -> None:
    start = _monday_on_or_before(date(2026, 6, 1))
    rows = [
        build_activity_row(
            activity(200 + i, (start + timedelta(days=i)).isoformat() + " 08:00:00", hr_zones=(600.0, 0.0, 0.0, 0.0, 0.0))
        )
        for i in range(21)
    ]
    # Actividad ancla sin carga (sin zonas de FC) para extender el rango de
    # fechas cubierto y simular una última semana totalmente en blanco.
    anchor_day = start + timedelta(days=27)
    rows.append(
        build_activity_row(
            activity(299, anchor_day.isoformat() + " 08:00:00", hr_zones=(None, None, None, None, None))
        )
    )

    weekly_totals = continuous_weekly_totals(rows)
    last = acwr_series(rows, weekly_totals)[-1]

    assert last.acute_7d_avg == pytest.approx(0.0)
    assert last.status == "bajo"


def test_acwr_sin_datos_when_no_training_load_available() -> None:
    # Rango de 28 días completo (para no disparar "historial insuficiente"),
    # pero ninguna actividad tiene datos de zona de FC.
    start = _monday_on_or_before(date(2026, 6, 1))
    later = start + timedelta(days=27)
    rows = [
        build_activity_row(activity(300, start.isoformat() + " 08:00:00", hr_zones=(None, None, None, None, None))),
        build_activity_row(activity(301, later.isoformat() + " 08:00:00", hr_zones=(None, None, None, None, None))),
    ]
    weekly_totals = continuous_weekly_totals(rows)
    last = acwr_series(rows, weekly_totals)[-1]

    assert last.ratio is None
    assert last.status == "sin datos"


def test_acwr_insufficient_history_in_early_weeks() -> None:
    # Con solo unos días de historial, la ventana crónica de 28 días está
    # parcialmente vacía -> no se puede dar un ACWR fiable todavía.
    start = _monday_on_or_before(date(2026, 6, 1))
    rows = [
        build_activity_row(activity(400, start.isoformat() + " 08:00:00", hr_zones=(600.0, 0.0, 0.0, 0.0, 0.0)))
    ]
    weekly_totals = continuous_weekly_totals(rows)
    first = acwr_series(rows, weekly_totals)[0]

    assert first.status == "historial insuficiente"
    assert first.ratio is None


def test_efficiency_factor_is_speed_over_hr_and_skips_total() -> None:
    rows = [
        build_activity_row(
            activity(1, "2026-09-14 08:00:00", sport="running", distance_m=10000, duration_s=3600, avg_hr=150.0)
        )
    ]
    ef_points = efficiency_factor_series(aggregate_by_week(rows))

    assert all(p.sport_key != TOTAL_SPORT_KEY for p in ef_points)
    running_point = next(p for p in ef_points if p.sport_key == "running")
    expected_speed_kmh = (10000 / 3600) * 3.6
    assert running_point.value == pytest.approx(expected_speed_kmh / 150.0, rel=1e-3)


def test_efficiency_factor_deltas_compare_to_last_practice_not_prior_calendar_week() -> None:
    rows = [
        build_activity_row(
            activity(1, "2026-09-01 08:00:00", sport="running", distance_m=10000, duration_s=3600, avg_hr=150.0)
        ),
        # semana intermedia: solo ciclismo, sin running
        build_activity_row(
            activity(2, "2026-09-08 08:00:00", sport="cycling", distance_m=30000, duration_s=3600, avg_hr=130.0)
        ),
        # running mejora su EF dos semanas después (no una)
        build_activity_row(
            activity(3, "2026-09-15 08:00:00", sport="running", distance_m=10000, duration_s=3000, avg_hr=150.0)
        ),
    ]
    from garmin_tracker.aggregates import aggregate_by_week

    deltas = efficiency_factor_deltas(aggregate_by_week(rows))
    running_deltas = [d for d in deltas if d.sport_key == "running"]

    assert running_deltas[0].delta_vs_prev_practice is None  # primera vez, nada con qué comparar
    assert running_deltas[1].delta_vs_prev_practice is not None
    assert running_deltas[1].delta_vs_prev_practice > 0  # corrió más rápido con la misma FC -> mejora


def test_personal_best_history_only_records_improvements() -> None:
    rows = [
        build_activity_row(activity(1, "2026-09-01 08:00:00", sport="running", fastestSplit_5000=1600.0)),
        build_activity_row(activity(2, "2026-09-08 08:00:00", sport="running", fastestSplit_5000=1700.0)),  # peor
        build_activity_row(activity(3, "2026-09-15 08:00:00", sport="running", fastestSplit_5000=1550.0)),  # mejor
    ]
    history = personal_best_history(rows)
    assert [pb.time_seconds for pb in history[5000]] == [1600.0, 1550.0]

    bests = current_personal_bests(rows)
    assert bests[5000].time_seconds == 1550.0
    assert bests[5000].activity_id == 3
