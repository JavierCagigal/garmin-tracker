"""Conversión del JSON crudo de una actividad (tal cual lo devuelve
`get_activities`) a una fila de datos lista para la hoja "Actividades".

Reglas de fidelidad: si un campo no está en el JSON, el valor de salida es
`None` (celda vacía en el Excel) — nunca se inventa ni se aproxima. Si el
campo SÍ está y vale 0 (p. ej. velocidad media en ciclismo indoor), se
respeta ese 0: es un dato real, no una ausencia de dato.

Estas funciones son puras: no tocan red, SQLite ni Excel, así que son
testeables con datos de ejemplo fijos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

SPORT_LABELS: dict[str, str] = {
    "running": "Correr",
    "trail_running": "Trail running",
    "track_running": "Atletismo en pista",
    "treadmill_running": "Cinta de correr",
    "indoor_cycling": "Ciclismo indoor",
    "cycling": "Ciclismo",
    "road_biking": "Ciclismo carretera",
    "mountain_biking": "BTT",
    "gravel_cycling": "Ciclismo gravel",
    "lap_swimming": "Natación en piscina",
    "open_water_swimming": "Natación en aguas abiertas",
    "strength_training": "Fuerza",
    "walking": "Caminar",
    "hiking": "Senderismo",
    "multi_sport": "Multideporte",
    "elliptical": "Elíptica",
    "yoga": "Yoga",
    "other": "Otro",
}

# El "ritmo min/km" solo tiene sentido para deportes de carrera/marcha; para
# ciclismo se usa km/h, y para natación un ritmo por 100m distinto — fuera de
# alcance por ahora. Calcularlo para otros deportes sería inventar una
# métrica sin significado real, así que se deja en blanco.
RUNNING_LIKE_SPORTS = {
    "running", "trail_running", "track_running", "treadmill_running", "walking", "hiking",
}

# Garmin usa un nombre de campo de cadencia distinto según el deporte.
CADENCE_FIELDS = (
    "averageRunningCadenceInStepsPerMinute",
    "averageBikingCadenceInRevPerMinute",
    "averageSwimCadenceInStrokesPerMinute",
)


@dataclass(frozen=True)
class ActivityRow:
    activity_id: int
    date: date
    start_time: time
    sport_key: str
    sport_label: str
    name: str
    distance_km: float | None
    duration: timedelta
    moving_duration: timedelta | None
    avg_pace_min_per_km: float | None
    avg_speed_kmh: float | None
    avg_hr: float | None
    max_hr: float | None
    elevation_gain_m: float | None
    calories: float | None
    avg_cadence: float | None
    avg_power: float | None
    aerobic_te: float | None
    anaerobic_te: float | None
    vo2max: float | None
    hr_zone_seconds: tuple[float | None, ...]
    temp_min_c: float | None
    temp_max_c: float | None


def _sport_label(sport_key: str) -> str:
    if sport_key in SPORT_LABELS:
        return SPORT_LABELS[sport_key]
    return sport_key.replace("_", " ").capitalize()


def _first_present(raw: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return float(value)
    return None


def build_activity_row(raw: dict[str, Any]) -> ActivityRow:
    start_local = datetime.strptime(raw["startTimeLocal"], "%Y-%m-%d %H:%M:%S")

    sport_key = (raw.get("activityType") or {}).get("typeKey", "unknown")
    distance_m = raw.get("distance")
    duration_seconds = raw.get("duration") or 0.0
    moving_seconds = raw.get("movingDuration")
    avg_speed_mps = raw.get("averageSpeed")

    avg_pace_min_per_km = None
    if avg_speed_mps is not None and avg_speed_mps > 0 and sport_key in RUNNING_LIKE_SPORTS:
        avg_pace_min_per_km = 1000 / avg_speed_mps / 60

    return ActivityRow(
        activity_id=raw["activityId"],
        date=start_local.date(),
        start_time=start_local.time(),
        sport_key=sport_key,
        sport_label=_sport_label(sport_key),
        name=raw.get("activityName") or "",
        distance_km=distance_m / 1000 if distance_m is not None else None,
        duration=timedelta(seconds=duration_seconds),
        moving_duration=timedelta(seconds=moving_seconds) if moving_seconds is not None else None,
        avg_pace_min_per_km=avg_pace_min_per_km,
        avg_speed_kmh=avg_speed_mps * 3.6 if avg_speed_mps is not None else None,
        avg_hr=raw.get("averageHR"),
        max_hr=raw.get("maxHR"),
        elevation_gain_m=raw.get("elevationGain"),
        calories=raw.get("calories"),
        avg_cadence=_first_present(raw, CADENCE_FIELDS),
        avg_power=raw.get("avgPower"),
        aerobic_te=raw.get("aerobicTrainingEffect"),
        anaerobic_te=raw.get("anaerobicTrainingEffect"),
        vo2max=raw.get("vO2MaxValue"),
        hr_zone_seconds=tuple(raw.get(f"hrTimeInZone_{i}") for i in range(1, 6)),
        temp_min_c=raw.get("minTemperature"),
        temp_max_c=raw.get("maxTemperature"),
    )
