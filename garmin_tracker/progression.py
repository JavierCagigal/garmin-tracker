"""Progresión: "¿he mejorado?" — ritmo sesión a sesión y mejores marcas.

Funciones puras: reciben `ActivityRow` ya calculados y devuelven datos, sin
tocar Garmin, SQLite ni Excel.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from garmin_tracker.activity_model import ActivityRow

STANDARD_DISTANCES_M: dict[int, str] = {
    1000: "1 km",
    5000: "5 km",
    10000: "10 km",
    21097: "Media maratón",
}


# --------------------------------------------------------------------------
# Ritmo sesión a sesión
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PaceDelta:
    vs_prev: float | None  # segundos; negativo = más rápido
    vs_avg4: float | None


def pace_deltas(paces: list[float | None]) -> list[PaceDelta]:
    """`paces` en segundos y en orden cronológico (None = sesión sin ritmo).
    Cada sesión se compara con la anterior que tenga ritmo y con la media de
    las (hasta) 4 anteriores con ritmo; con menos de 2 no hay media fiable."""
    deltas: list[PaceDelta] = []
    seen: list[float] = []
    for pace in paces:
        if pace is None:
            deltas.append(PaceDelta(None, None))
            continue
        last4 = seen[-4:]
        deltas.append(
            PaceDelta(
                vs_prev=pace - seen[-1] if seen else None,
                vs_avg4=pace - sum(last4) / len(last4) if len(last4) >= 2 else None,
            )
        )
        seen.append(pace)
    return deltas


# --------------------------------------------------------------------------
# Mejores marcas por distancia estándar
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PersonalBest:
    distance_m: int
    distance_label: str
    time_seconds: float
    achieved_on: date
    activity_id: int
    activity_name: str


def personal_best_history(rows: list[ActivityRow]) -> dict[int, list[PersonalBest]]:
    """Para cada distancia estándar, la secuencia de récords según se
    batieron en el tiempo (créciente en fecha, decreciente en tiempo)."""
    history: dict[int, list[PersonalBest]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: (r.date, r.start_time)):
        for distance_m, time_seconds in r.best_splits.items():
            if distance_m not in STANDARD_DISTANCES_M:
                continue
            existing = history[distance_m]
            if not existing or time_seconds < existing[-1].time_seconds:
                existing.append(
                    PersonalBest(
                        distance_m=distance_m,
                        distance_label=STANDARD_DISTANCES_M[distance_m],
                        time_seconds=time_seconds,
                        achieved_on=r.date,
                        activity_id=r.activity_id,
                        activity_name=r.name,
                    )
                )
    return dict(history)


def current_personal_bests(rows: list[ActivityRow]) -> dict[int, PersonalBest]:
    history = personal_best_history(rows)
    return {distance_m: records[-1] for distance_m, records in history.items() if records}
