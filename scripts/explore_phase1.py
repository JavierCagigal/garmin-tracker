#!/usr/bin/env python3
"""Fase 1: conectar a Garmin, bajar las últimas 10 actividades y volcar el
JSON crudo tal cual lo devuelve la API, para validar qué campos hay de
verdad antes de modelar nada.

Uso:
    ./.venv/bin/python scripts/explore_phase1.py

Si la cuenta tiene MFA activado, la primera ejecución pedirá el código por
terminal (necesita stdin interactivo). Ejecuciones posteriores reutilizan el
token cacheado y no deberían pedir nada.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garmin_tracker.config import load_settings
from garmin_tracker.garmin_client import get_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("explore_phase1")

DEBUG_DIR = Path(__file__).resolve().parent.parent / "debug"


def main() -> None:
    settings = load_settings()
    if not settings.garmin_email or not settings.garmin_password:
        logger.error("Faltan GARMIN_EMAIL / GARMIN_PASSWORD en .env (copia .env.example).")
        sys.exit(1)

    DEBUG_DIR.mkdir(exist_ok=True)

    client = get_client(settings)

    logger.info("Descargando las últimas 10 actividades (resumen de lista)...")
    activities = client.get_activities(start=0, limit=10)
    print("\n=== get_activities(start=0, limit=10) -> resumen de lista ===\n")
    print(json.dumps(activities, indent=2, ensure_ascii=False))

    list_path = DEBUG_DIR / "last10_activities.json"
    list_path.write_text(json.dumps(activities, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Volcado también en %s", list_path)

    if not activities:
        logger.warning("La cuenta no tiene actividades. Nada más que inspeccionar.")
        return

    first = activities[0]
    activity_id = first["activityId"]
    logger.info("Pidiendo detalle completo de la actividad %s ('%s')...", activity_id, first.get("activityName"))

    detail = client.get_activity(str(activity_id))

    hr_zones = None
    try:
        hr_zones = client.get_activity_hr_in_timezones(str(activity_id))
    except Exception as exc:  # noqa: BLE001 - exploración, queremos ver qué falla
        logger.warning("get_activity_hr_in_timezones falló para %s: %s", activity_id, exc)

    weather = None
    try:
        weather = client.get_activity_weather(str(activity_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_activity_weather falló para %s: %s", activity_id, exc)

    sample = {
        "activity_detail": detail,
        "hr_time_in_zones": hr_zones,
        "weather": weather,
    }
    print(f"\n=== get_activity({activity_id}) + hrTimeInZones + weather ===\n")
    print(json.dumps(sample, indent=2, ensure_ascii=False))

    sample_path = DEBUG_DIR / "activity_detail_sample.json"
    sample_path.write_text(json.dumps(sample, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Volcado también en %s", sample_path)

    logger.info("Hecho. Revisa los JSON de arriba (y los ficheros en debug/) antes de seguir.")


if __name__ == "__main__":
    main()
