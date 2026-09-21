"""Datos de ejemplo fijos (actividades reales simplificadas, con la misma
forma que devuelve get_activities) usados por varios test_*.py."""

from __future__ import annotations

from typing import Any


def running_activity(
    activity_id: int = 1001,
    start_time_local: str = "2026-09-20 09:13:31",
    distance_m: float = 10018.74,
    duration_s: float = 3100.489,
    avg_hr: float = 143.0,
) -> dict[str, Any]:
    return {
        "activityId": activity_id,
        "activityName": "Carrera de prueba",
        "startTimeLocal": start_time_local,
        "activityType": {"typeKey": "running"},
        "distance": distance_m,
        "duration": duration_s,
        "movingDuration": duration_s - 3,
        "elapsedDuration": duration_s,
        "elevationGain": 110.0,
        "averageSpeed": distance_m / duration_s,
        "calories": 758.0,
        "averageHR": avg_hr,
        "maxHR": 158.0,
        "averageRunningCadenceInStepsPerMinute": 166.8,
        "avgPower": 375.0,
        "aerobicTrainingEffect": 3.4,
        "anaerobicTrainingEffect": 0.0,
        "vO2MaxValue": 59.0,
        "hrTimeInZone_1": 37.0,
        "hrTimeInZone_2": 381.0,
        "hrTimeInZone_3": 2579.6,
        "hrTimeInZone_4": 81.0,
        "hrTimeInZone_5": 0.0,
        "minTemperature": 20.0,
        "maxTemperature": 26.0,
    }


def indoor_cycling_activity(
    activity_id: int = 1002,
    start_time_local: str = "2026-09-19 13:39:05",
    duration_s: float = 3614.9,
    avg_hr: float = 113.0,
) -> dict[str, Any]:
    return {
        "activityId": activity_id,
        "activityName": "Ciclismo en sala",
        "startTimeLocal": start_time_local,
        "activityType": {"typeKey": "indoor_cycling"},
        "distance": 0.0,
        "duration": duration_s,
        "movingDuration": 0.0,
        "averageSpeed": 0.0,
        "calories": 453.0,
        "averageHR": avg_hr,
        "maxHR": 132.0,
        "aerobicTrainingEffect": 2.0,
        "anaerobicTrainingEffect": 0.0,
        "hrTimeInZone_1": 2048.0,
        "hrTimeInZone_2": 1348.0,
        "hrTimeInZone_3": 0.0,
        "hrTimeInZone_4": 0.0,
        "hrTimeInZone_5": 0.0,
        "minTemperature": 27.0,
        "maxTemperature": 30.0,
    }


def strength_activity(
    activity_id: int = 1003,
    start_time_local: str = "2026-09-18 20:48:27",
    duration_s: float = 2232.75,
) -> dict[str, Any]:
    return {
        "activityId": activity_id,
        "activityName": "Fuerza",
        "startTimeLocal": start_time_local,
        "activityType": {"typeKey": "strength_training"},
        "distance": 0.0,
        "duration": duration_s,
        "movingDuration": 775.3,
        "averageSpeed": 0.0,
        "calories": 232.0,
        "averageHR": 100.0,
        "maxHR": 138.0,
        "aerobicTrainingEffect": 0.7,
        "anaerobicTrainingEffect": 0.1,
        "hrTimeInZone_1": 964.3,
        "hrTimeInZone_2": 253.3,
        "hrTimeInZone_3": 5.0,
        "hrTimeInZone_4": 0.0,
        "hrTimeInZone_5": 0.0,
        # Sin minTemperature/maxTemperature a propósito: simula un campo
        # que Garmin no devuelve para esta actividad.
    }
