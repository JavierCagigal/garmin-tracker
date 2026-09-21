"""Agregados semanales (semana ISO) por deporte y total.

Funciones puras: reciben `ActivityRow` ya calculados y devuelven datos, sin
tocar Garmin, SQLite ni Excel.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from garmin_tracker.activity_model import ActivityRow

TOTAL_SPORT_KEY = "__total__"
TOTAL_SPORT_LABEL = "Total"


@dataclass(frozen=True)
class WeeklyAggregate:
    iso_year: int
    iso_week: int
    sport_key: str  # TOTAL_SPORT_KEY para el agregado de todos los deportes
    sport_label: str
    sessions: int
    total_distance_km: float
    total_duration: timedelta
    total_elevation_gain_m: float
    # Ritmo ponderado por distancia (no la media de las medias): solo se
    # calcula sobre las sesiones donde el ritmo tiene sentido (carrera/marcha).
    weighted_avg_pace_min_per_km: float | None
    # FC media ponderada por tiempo de sesión.
    weighted_avg_hr: float | None
    weighted_avg_speed_kmh: float | None
    # None = sin datos de FC esa semana; 0.0 = semana sin ninguna sesión.
    training_load: float | None
    pct_time_easy: float | None  # % tiempo en zonas 1-2
    pct_time_intense: float | None  # % tiempo en zonas 3-5


def iso_week_key(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return (iso.year, iso.week)


def _weighted_pace(rows: list[ActivityRow]) -> float | None:
    total_seconds = 0.0
    total_km = 0.0
    for r in rows:
        if r.avg_pace_min_per_km is None or not r.distance_km:
            continue
        total_seconds += r.duration.total_seconds()
        total_km += r.distance_km
    if total_km <= 0:
        return None
    return (total_seconds / 60) / total_km


def _weighted_avg(rows: list[ActivityRow], value_fn) -> float | None:
    total_weighted = 0.0
    total_seconds = 0.0
    for r in rows:
        value = value_fn(r)
        if value is None:
            continue
        seconds = r.duration.total_seconds()
        total_weighted += value * seconds
        total_seconds += seconds
    if total_seconds <= 0:
        return None
    return total_weighted / total_seconds


def _zone_split(rows: list[ActivityRow]) -> tuple[float | None, float | None]:
    easy = 0.0
    intense = 0.0
    any_data = False
    for r in rows:
        zones = r.hr_zone_seconds
        if all(z is None for z in zones):
            continue
        any_data = True
        easy += (zones[0] or 0.0) + (zones[1] or 0.0)
        intense += (zones[2] or 0.0) + (zones[3] or 0.0) + (zones[4] or 0.0)
    total = easy + intense
    if not any_data or total <= 0:
        return None, None
    return easy / total * 100, intense / total * 100


def build_week_aggregate(
    iso_year: int, iso_week: int, sport_key: str, sport_label: str, rows: list[ActivityRow]
) -> WeeklyAggregate:
    if not rows:
        # Semana real sin ninguna sesión: la carga es 0 de verdad (descanso),
        # no "desconocida".
        training_load: float | None = 0.0
    else:
        loads = [r.training_load for r in rows if r.training_load is not None]
        training_load = sum(loads) if loads else None

    pct_easy, pct_intense = _zone_split(rows)

    return WeeklyAggregate(
        iso_year=iso_year,
        iso_week=iso_week,
        sport_key=sport_key,
        sport_label=sport_label,
        sessions=len(rows),
        total_distance_km=sum(r.distance_km or 0.0 for r in rows),
        total_duration=sum((r.duration for r in rows), timedelta()),
        total_elevation_gain_m=sum(r.elevation_gain_m or 0.0 for r in rows),
        weighted_avg_pace_min_per_km=_weighted_pace(rows),
        weighted_avg_hr=_weighted_avg(rows, lambda r: r.avg_hr),
        weighted_avg_speed_kmh=_weighted_avg(rows, lambda r: r.avg_speed_kmh),
        training_load=training_load,
        pct_time_easy=pct_easy,
        pct_time_intense=pct_intense,
    )


def moving_average(values: list[float], window: int) -> list[float]:
    """Media móvil hacia atrás INCLUYENDO el punto actual (a diferencia de
    la media de 4 semanas de progression.py, que compara contra las 4
    semanas ANTERIORES). Pensada para dibujar una línea de tendencia
    superpuesta sobre un gráfico de barras: al principio de la serie, antes
    de tener `window` puntos completos, promedia los que haya disponibles
    en vez de dejarlo en blanco.
    """
    result: list[float] = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1): i + 1]
        result.append(sum(chunk) / len(chunk))
    return result


def aggregate_by_week(rows: list[ActivityRow]) -> list[WeeklyAggregate]:
    """Una fila TOTAL + una fila por deporte practicado, para cada semana
    ISO que tenga al menos una actividad. Orden cronológico ascendente."""
    by_week: dict[tuple[int, int], list[ActivityRow]] = defaultdict(list)
    for r in rows:
        by_week[iso_week_key(r.date)].append(r)

    results: list[WeeklyAggregate] = []
    for (iso_year, iso_week) in sorted(by_week):
        week_rows = by_week[(iso_year, iso_week)]
        results.append(build_week_aggregate(iso_year, iso_week, TOTAL_SPORT_KEY, TOTAL_SPORT_LABEL, week_rows))

        by_sport: dict[str, list[ActivityRow]] = defaultdict(list)
        for r in week_rows:
            by_sport[r.sport_key].append(r)
        for sport_key in sorted(by_sport):
            sport_rows = by_sport[sport_key]
            results.append(
                build_week_aggregate(iso_year, iso_week, sport_key, sport_rows[0].sport_label, sport_rows)
            )

    return results
