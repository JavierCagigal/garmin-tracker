#!/usr/bin/env python3
"""Genera el panel web (output/entrenamientos.html) a partir de la caché SQLite.
No toca el Excel.

Uso:
    ./.venv/bin/python scripts/generate_web.py
"""

from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garmin_tracker import storage
from garmin_tracker.activity_model import build_activity_row
from garmin_tracker.config import load_settings
from garmin_tracker.logging_config import setup_logging
from garmin_tracker.progression import current_personal_bests
from garmin_tracker.web import build_dashboard_data, write_dashboard

logger = logging.getLogger("generate_web")


def main() -> int:
    setup_logging()
    settings = load_settings()

    conn = storage.connect(settings.db_path)
    try:
        raw_activities = storage.all_raw_activities(conn)
    finally:
        conn.close()

    if not raw_activities:
        logger.warning("La caché no tiene actividades todavía. Ejecuta antes scripts/sync.py.")
        return 1

    rows = [build_activity_row(raw) for raw in raw_activities]
    out_path = settings.excel_path.with_name("entrenamientos.html")
    write_dashboard(out_path, build_dashboard_data(rows, current_personal_bests(rows), date.today()))
    logger.info("Panel web escrito en %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
