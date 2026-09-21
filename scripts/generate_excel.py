#!/usr/bin/env python3
"""Genera/actualiza el Excel a partir de la caché SQLite.

Uso:
    ./.venv/bin/python scripts/generate_excel.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garmin_tracker import storage
from garmin_tracker.activity_model import build_activity_row
from garmin_tracker.config import load_settings
from garmin_tracker.excel_book import write_workbook
from garmin_tracker.logging_config import setup_logging

logger = logging.getLogger("generate_excel")


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
    logger.info("Generando Excel con %d actividades...", len(rows))

    write_workbook(rows, settings.excel_path)
    logger.info("Excel escrito en %s", settings.excel_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
