"""Comparativas semana a semana: "¿he mejorado?".

Funciones puras: reciben `ActivityRow`/`WeeklyAggregate` ya calculados y
devuelven datos, sin tocar Garmin, SQLite ni Excel.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from garmin_tracker.activity_model import ActivityRow
from garmin_tracker.aggregates import (
    TOTAL_SPORT_KEY,
    TOTAL_SPORT_LABEL,
    WeeklyAggregate,
    build_week_aggregate,
    iso_week_key,
)

# Una sola sesión en la semana no da para concluir tendencia: no comparable.
MIN_SESSIONS_FOR_COMPARISON = 2

# Rango de referencia estándar en literatura de ciencias del deporte
# (Gabbett, 2016) para el ratio de carga aguda:crónica.
ACWR_SAFE_RANGE = (0.8, 1.3)

STANDARD_DISTANCES_M: dict[int, str] = {
    1000: "1 km",
    5000: "5 km",
    10000: "10 km",
    21097: "Media maratón",
}


# --------------------------------------------------------------------------
# Serie semanal continua (incluye semanas de descanso con 0 sesiones), base
# para deltas y ACWR: hace falta que "la semana pasada" sea de verdad la
# semana ISO anterior, no "la semana anterior en la que entrenaste".
# --------------------------------------------------------------------------


def _all_iso_weeks_between(start: date, end: date) -> list[tuple[int, int]]:
    weeks: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    current = start
    while current <= end:
        key = iso_week_key(current)
        if key not in seen:
            seen.add(key)
            weeks.append(key)
        current += timedelta(days=1)
    return weeks


def continuous_weekly_totals(rows: list[ActivityRow]) -> list[WeeklyAggregate]:
    if not rows:
        return []
    dates = [r.date for r in rows]
    all_weeks = _all_iso_weeks_between(min(dates), max(dates))

    by_week: dict[tuple[int, int], list[ActivityRow]] = defaultdict(list)
    for r in rows:
        by_week[iso_week_key(r.date)].append(r)

    return [
        build_week_aggregate(iso_year, iso_week, TOTAL_SPORT_KEY, TOTAL_SPORT_LABEL, by_week.get((iso_year, iso_week), []))
        for iso_year, iso_week in all_weeks
    ]


# --------------------------------------------------------------------------
# Δ vs semana anterior y Δ vs media móvil de 4 semanas
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricDelta:
    value: float | None
    delta_vs_prev: float | None
    pct_vs_prev: float | None
    delta_vs_ma4: float | None
    pct_vs_ma4: float | None


@dataclass(frozen=True)
class WeeklyComparison:
    iso_year: int
    iso_week: int
    sessions: int
    comparable: bool  # False si sessions < MIN_SESSIONS_FOR_COMPARISON
    volume_km: MetricDelta
    duration_min: MetricDelta
    training_load: MetricDelta
    pace_min_per_km: MetricDelta  # ¡ojo!: en ritmo, "mejora" = valor MÁS BAJO


def _pct(delta: float | None, base: float | None) -> float | None:
    if delta is None or base is None or base == 0:
        return None
    return delta / base * 100


def _metric_delta(values: list[float | None], index: int) -> MetricDelta:
    value = values[index]
    prev = values[index - 1] if index >= 1 else None

    window = values[max(0, index - 4):index]
    ma4 = sum(window) / len(window) if len(window) == 4 and all(v is not None for v in window) else None

    delta_prev = (value - prev) if value is not None and prev is not None else None
    delta_ma4 = (value - ma4) if value is not None and ma4 is not None else None

    return MetricDelta(
        value=value,
        delta_vs_prev=delta_prev,
        pct_vs_prev=_pct(delta_prev, prev),
        delta_vs_ma4=delta_ma4,
        pct_vs_ma4=_pct(delta_ma4, ma4),
    )


def compute_weekly_deltas(weekly_totals: list[WeeklyAggregate]) -> list[WeeklyComparison]:
    """`weekly_totals` debe ser la serie CONTINUA (ver continuous_weekly_totals),
    en orden cronológico ascendente, o los "4 semanas anteriores" no serán
    semanas de calendario reales."""
    volumes = [w.total_distance_km for w in weekly_totals]
    durations_min = [w.total_duration.total_seconds() / 60 for w in weekly_totals]
    loads = [w.training_load for w in weekly_totals]
    paces = [w.weighted_avg_pace_min_per_km for w in weekly_totals]

    comparisons = []
    for i, w in enumerate(weekly_totals):
        comparisons.append(
            WeeklyComparison(
                iso_year=w.iso_year,
                iso_week=w.iso_week,
                sessions=w.sessions,
                comparable=w.sessions >= MIN_SESSIONS_FOR_COMPARISON,
                volume_km=_metric_delta(volumes, i),
                duration_min=_metric_delta(durations_min, i),
                training_load=_metric_delta(loads, i),
                pace_min_per_km=_metric_delta(paces, i),
            )
        )
    return comparisons


# --------------------------------------------------------------------------
# Ratio de carga aguda:crónica (ACWR)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AcwrPoint:
    iso_year: int
    iso_week: int
    as_of: date  # domingo (último día) de esa semana ISO
    acute_7d_avg: float | None  # carga media diaria, últimos 7 días
    chronic_28d_avg: float | None  # carga media diaria, últimos 28 días
    ratio: float | None
    status: str  # "ok" | "alto" | "bajo" | "sin datos" | "historial insuficiente"


def daily_training_load(rows: list[ActivityRow]) -> dict[date, float]:
    daily: dict[date, float] = defaultdict(float)
    for r in rows:
        if r.training_load is not None:
            daily[r.date] += r.training_load
    return dict(daily)


def _window_avg(daily: dict[date, float], as_of: date, days: int) -> float:
    total = sum(daily.get(as_of - timedelta(days=offset), 0.0) for offset in range(days))
    return total / days


def acwr_series(rows: list[ActivityRow], weekly_totals: list[WeeklyAggregate]) -> list[AcwrPoint]:
    """ACWR = (carga media diaria, últimos 7 días) / (carga media diaria,
    últimos 28 días) — el ratio estándar de la literatura de ciencias del
    deporte, cuyo rango de referencia 0.8-1.3 es el que se usa como aviso.

    Si todavía no hay 28 días reales de historial antes de esa semana (p.ej.
    las primeras semanas de uso), la ventana "crónica" está parcialmente
    vacía y el ratio saldría artificialmente alto — se marca explícitamente
    como "historial insuficiente" en vez de dar un aviso engañoso.
    """
    daily = daily_training_load(rows)
    if not rows:
        return []
    earliest_date = min(r.date for r in rows)

    points = []
    for w in weekly_totals:
        as_of = date.fromisocalendar(w.iso_year, w.iso_week, 7)  # domingo
        acute = _window_avg(daily, as_of, 7)
        chronic = _window_avg(daily, as_of, 28)
        chronic_window_start = as_of - timedelta(days=27)

        if chronic_window_start < earliest_date:
            ratio = None
            status = "historial insuficiente"
        elif chronic <= 0:
            ratio = None
            status = "sin datos"
        else:
            ratio = acute / chronic
            if ratio < ACWR_SAFE_RANGE[0]:
                status = "bajo"
            elif ratio > ACWR_SAFE_RANGE[1]:
                status = "alto"
            else:
                status = "ok"

        points.append(
            AcwrPoint(
                iso_year=w.iso_year,
                iso_week=w.iso_week,
                as_of=as_of,
                acute_7d_avg=acute,
                chronic_28d_avg=chronic,
                ratio=ratio,
                status=status,
            )
        )
    return points


# --------------------------------------------------------------------------
# Efficiency Factor (velocidad media / FC media) por deporte y semana
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EfficiencyFactorPoint:
    iso_year: int
    iso_week: int
    sport_key: str
    sport_label: str
    sessions: int
    value: float | None  # (km/h) / (lpm)


def efficiency_factor_series(weekly_aggregates: list[WeeklyAggregate]) -> list[EfficiencyFactorPoint]:
    points = []
    for w in weekly_aggregates:
        if w.sport_key == TOTAL_SPORT_KEY:
            continue
        ef = None
        if w.weighted_avg_speed_kmh and w.weighted_avg_hr:
            ef = w.weighted_avg_speed_kmh / w.weighted_avg_hr
        points.append(
            EfficiencyFactorPoint(
                iso_year=w.iso_year,
                iso_week=w.iso_week,
                sport_key=w.sport_key,
                sport_label=w.sport_label,
                sessions=w.sessions,
                value=ef,
            )
        )
    return points


@dataclass(frozen=True)
class EfficiencyFactorDelta:
    iso_year: int
    iso_week: int
    sport_key: str
    sport_label: str
    sessions: int
    value: float | None
    delta_vs_prev_practice: float | None  # vs. la última vez que se practicó ESE deporte
    pct_vs_prev_practice: float | None


def efficiency_factor_deltas(weekly_aggregates: list[WeeklyAggregate]) -> list[EfficiencyFactorDelta]:
    """Compara el EF de cada semana con el de la última vez que se practicó
    ese mismo deporte (no con la semana de calendario anterior, que podría
    ser de otro deporte o no tener ninguna sesión de este)."""
    last_value_by_sport: dict[str, float] = {}
    deltas = []
    for p in efficiency_factor_series(weekly_aggregates):
        prev = last_value_by_sport.get(p.sport_key)
        delta = (p.value - prev) if p.value is not None and prev is not None else None
        deltas.append(
            EfficiencyFactorDelta(
                iso_year=p.iso_year,
                iso_week=p.iso_week,
                sport_key=p.sport_key,
                sport_label=p.sport_label,
                sessions=p.sessions,
                value=p.value,
                delta_vs_prev_practice=delta,
                pct_vs_prev_practice=_pct(delta, prev),
            )
        )
        if p.value is not None:
            last_value_by_sport[p.sport_key] = p.value
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
