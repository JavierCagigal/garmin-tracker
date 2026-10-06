from __future__ import annotations

import pytest

from garmin_tracker.activity_model import build_activity_row
from garmin_tracker.progression import current_personal_bests, pace_deltas, personal_best_history
from tests.fixtures import activity


def test_pace_deltas_vs_previous_and_avg_of_last_four() -> None:
    # 300, 310, (sesión sin ritmo), 290, 320, 280 segundos
    deltas = pace_deltas([300, 310, None, 290, 320, 280])

    assert deltas[0].vs_prev is None and deltas[0].vs_avg4 is None  # nada con qué comparar
    assert deltas[1].vs_prev == 10 and deltas[1].vs_avg4 is None  # 1 previa: sin media
    assert deltas[2].vs_prev is None  # sesión sin ritmo
    assert deltas[3].vs_prev == -20  # se compara con 310, se salta la sin ritmo
    assert deltas[3].vs_avg4 == pytest.approx(290 - 305)
    # media de las 4 anteriores con ritmo: 300, 310, 290, 320 -> 305
    assert deltas[5].vs_prev == -40
    assert deltas[5].vs_avg4 == pytest.approx(280 - 305)


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
