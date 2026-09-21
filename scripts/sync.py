#!/usr/bin/env python3
"""Punto de entrada: sincroniza actividades de Garmin Connect a la caché local.

Uso:
    ./.venv/bin/python scripts/sync.py                     # incremental
    ./.venv/bin/python scripts/sync.py --full               # todo el histórico
    ./.venv/bin/python scripts/sync.py --desde 2026-01-01    # desde una fecha
    ./.venv/bin/python scripts/sync.py --dry-run             # simular, sin escribir
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garmin_tracker.cli import main

if __name__ == "__main__":
    sys.exit(main())
