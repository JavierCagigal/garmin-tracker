"""Carga de configuración desde variables de entorno (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    garmin_email: str | None
    garmin_password: str | None
    tokenstore: str
    db_path: Path
    excel_path: Path


def load_settings() -> Settings:
    return Settings(
        garmin_email=os.getenv("GARMIN_EMAIL"),
        garmin_password=os.getenv("GARMIN_PASSWORD"),
        tokenstore=os.getenv("GARMIN_TOKENSTORE", "~/.garminconnect"),
        db_path=Path(os.getenv("GARMIN_DB_PATH", "./data/garmin_cache.db")),
        excel_path=Path(os.getenv("GARMIN_EXCEL_PATH", "./output/entrenamientos.xlsx")),
    )
