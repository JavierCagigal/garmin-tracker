"""CLI de sincronización: `python scripts/sync.py [--full] [--desde YYYY-MM-DD] [--dry-run]`."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from garmin_tracker import storage
from garmin_tracker.config import load_settings
from garmin_tracker.garmin_client import get_client
from garmin_tracker.logging_config import setup_logging
from garmin_tracker.sync import run_sync

logger = logging.getLogger("garmin_tracker.cli")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sincroniza actividades de Garmin Connect a la caché local (SQLite)."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--full", action="store_true",
        help="Rehace la descarga completa del histórico disponible, ignorando la caché.",
    )
    group.add_argument(
        "--desde", type=str, metavar="YYYY-MM-DD",
        help="Descarga actividades desde esta fecha (inclusive), ignorando la caché.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="No escribe nada en la caché, solo muestra qué se descargaría.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging()

    since = None
    if args.desde:
        try:
            since = datetime.strptime(args.desde, "%Y-%m-%d").date()
        except ValueError:
            logger.error("--desde debe tener formato YYYY-MM-DD, recibido: %s", args.desde)
            return 2

    settings = load_settings()
    if not settings.garmin_email or not settings.garmin_password:
        logger.error("Faltan GARMIN_EMAIL / GARMIN_PASSWORD en .env (copia .env.example).")
        return 2

    conn = storage.connect(settings.db_path)
    try:
        client = get_client(settings)
        result = run_sync(client, conn, full=args.full, since=since, dry_run=args.dry_run)
        if not args.dry_run:
            logger.info("La caché tiene ahora %d actividades en total.", storage.count_activities(conn))
    finally:
        conn.close()

    logger.info(
        "Hecho: %d nuevas, %d actualizadas, %d páginas.",
        result.new_count, result.updated_count, result.pages_fetched,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
