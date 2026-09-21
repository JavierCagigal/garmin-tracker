"""Sincronización incremental de actividades desde Garmin Connect a la caché
local.

Estrategia: `get_activities(start, limit)` siempre devuelve las actividades
en orden de más reciente a más antigua. Aprovechamos ese orden para no
depender de rangos de fecha del lado del servidor:

- full: pagina hasta que una página viene vacía (todo el histórico).
- desde=X: pagina hasta que una actividad tiene start_time_local anterior a X.
- incremental (por defecto): pagina hasta encontrar un activity_id que ya
  está en caché — a partir de ahí, todo lo siguiente (más antiguo) ya lo
  tenemos también, así que paramos.

Cada página se escribe (commit) en cuanto se descarga, así una interrupción
a mitad de una sincronización grande no pierde el progreso ya hecho.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Protocol

from garmin_tracker import storage
from garmin_tracker.retry import call_with_retry

logger = logging.getLogger(__name__)

PAGE_SIZE = 50


class ActivitiesClient(Protocol):
    def get_activities(self, start: int, limit: int) -> list[dict[str, Any]]: ...


@dataclass
class SyncResult:
    mode: str
    pages_fetched: int
    activities_seen: int
    new_count: int
    updated_count: int
    dry_run: bool


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_pages(
    client: ActivitiesClient,
    *,
    stop_at_known_id: set[int] | None,
    stop_before_date: str | None,
) -> Iterator[list[dict[str, Any]]]:
    start = 0
    while True:
        page = call_with_retry(
            lambda: client.get_activities(start=start, limit=PAGE_SIZE),
            description=f"get_activities(start={start}, limit={PAGE_SIZE})",
        )
        if not page:
            return

        filtered_page = []
        cutoff_hit = False
        for activity in page:
            activity_id = activity["activityId"]
            start_time_local = activity.get("startTimeLocal", "")
            if stop_at_known_id is not None and activity_id in stop_at_known_id:
                cutoff_hit = True
                break
            if stop_before_date is not None and start_time_local < stop_before_date:
                cutoff_hit = True
                break
            filtered_page.append(activity)

        if filtered_page:
            yield filtered_page

        if cutoff_hit or len(page) < PAGE_SIZE:
            return
        start += PAGE_SIZE


def run_sync(
    client: ActivitiesClient,
    conn: sqlite3.Connection,
    *,
    full: bool = False,
    since: date | None = None,
    dry_run: bool = False,
) -> SyncResult:
    existing_ids_before = storage.existing_activity_ids(conn)

    if full:
        mode = "full"
        stop_at_known_id: set[int] | None = None
        stop_before_date: str | None = None
    elif since is not None:
        mode = "desde"
        stop_at_known_id = None
        stop_before_date = since.isoformat()
    elif not existing_ids_before:
        mode = "full (primera ejecución, caché vacía)"
        stop_at_known_id = None
        stop_before_date = None
    else:
        mode = "incremental"
        stop_at_known_id = existing_ids_before
        stop_before_date = None

    logger.info("Modo de sincronización: %s%s", mode, " [dry-run]" if dry_run else "")

    pages_fetched = 0
    activities_seen = 0
    new_count = 0
    updated_count = 0
    fetched_at = _now_iso()

    for page in _fetch_pages(client, stop_at_known_id=stop_at_known_id, stop_before_date=stop_before_date):
        pages_fetched += 1
        activities_seen += len(page)
        for activity in page:
            if activity["activityId"] in existing_ids_before:
                updated_count += 1
            else:
                new_count += 1
            if not dry_run:
                storage.upsert_activity(conn, activity, fetched_at)
        if not dry_run:
            conn.commit()
        logger.info(
            "Página %d: %d actividades descargadas (%d nuevas, %d actualizadas hasta ahora).",
            pages_fetched, len(page), new_count, updated_count,
        )

    logger.info(
        "Sync (%s) terminado. Páginas: %d, actividades vistas: %d, nuevas: %d, actualizadas: %d.%s",
        mode, pages_fetched, activities_seen, new_count, updated_count,
        " (dry-run: no se ha escrito nada en la caché)" if dry_run else "",
    )

    return SyncResult(
        mode=mode,
        pages_fetched=pages_fetched,
        activities_seen=activities_seen,
        new_count=new_count,
        updated_count=updated_count,
        dry_run=dry_run,
    )
