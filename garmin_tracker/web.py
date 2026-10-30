"""Panel web (output/entrenamientos.html): una sola página estática con los
mismos datos y métricas que el Excel (excel_charts.SPORTS), pero más visual.

Los datos van incrustados como JSON dentro del HTML, así que se abre con
doble clic, sin servidor. No incluye coordenadas GPS: la página se puede
publicar sin revelar dónde se entrena.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from garmin_tracker.activity_model import ActivityRow
from garmin_tracker.aggregates import moving_average
from garmin_tracker.excel_charts import SPORTS, weekly_buckets
from garmin_tracker.progression import STANDARD_DISTANCES_M, PersonalBest

TEMPLATE = Path(__file__).with_name("web_template.html")


def _num(value: float | timedelta | None) -> float | None:
    """Ritmos en segundos; el resto, redondeado para no inflar el JSON."""
    if isinstance(value, timedelta):
        return round(value.total_seconds(), 1)
    return round(value, 2) if value is not None else None


def _minutes(rows: list[ActivityRow]) -> float:
    return round(sum(r.duration.total_seconds() for r in rows) / 60, 1)


def _sport_of(r: ActivityRow) -> tuple[str, int]:
    """Nombre y color (posición en SPORTS, 1..n; 0 = sin color, p. ej. Caminar)."""
    for slot, sport in enumerate(SPORTS, start=1):
        if r.sport_key in sport.keys:
            return sport.name, slot
    return r.sport_label, 0


def build_dashboard_data(rows: list[ActivityRow], personal_bests: dict[int, PersonalBest], generated: date) -> dict:
    mondays, by_week = weekly_buckets(rows)
    weeks_all = [by_week.get(m, []) for m in mondays]

    sports = []
    for slot, sport in enumerate(SPORTS, start=1):
        weeks = [[r for r in w if r.sport_key in sport.keys] for w in weeks_all]
        sessions = sorted((r for w in weeks for r in w), key=lambda r: (r.date, r.start_time))
        if not sessions:
            continue
        pace = next((m for m in sport.metrics if m.number_format == "m:ss"), None)
        sports.append({
            "name": sport.name,
            "slot": slot,
            "metrics": [
                {
                    "name": m.name,
                    "unit": m.unit,
                    "format": m.number_format,
                    "chart": m.chart,
                    # Semana sin sesiones = null, como la fila vacía del Excel.
                    "values": [_num(m.compute(w)) if w else None for w in weeks],
                }
                for m in sport.metrics
            ],
            "minutes": [_minutes(w) for w in weeks],
            "sessions": [
                {
                    "date": r.date.isoformat(),
                    "name": r.name,
                    "minutes": _minutes([r]),
                    "km": _num(r.distance_km),
                    "pace": _num(pace.compute([r])) if pace else None,
                    "hr": r.avg_hr,
                    "hour": r.start_time.hour,
                    "cadence": round(r.avg_cadence) if r.avg_cadence else None,
                    "power": r.avg_power,
                    "te": _num(r.aerobic_te),
                }
                for r in sessions
            ],
        })

    chronological = sorted(rows, key=lambda r: (r.date, r.start_time))
    # Para el calendario de constancia: minutos y deportes de cada día.
    days: dict[str, dict] = {}
    for r in chronological:
        day = days.setdefault(r.date.isoformat(), {"minutes": 0.0, "sports": []})
        day["minutes"] = round(day["minutes"] + r.duration.total_seconds() / 60, 1)
        if _sport_of(r)[0] not in day["sports"]:
            day["sports"].append(_sport_of(r)[0])

    recent = chronological[::-1][:12]
    # Semana sin FC = carga 0 (en Semanal del Excel sería celda vacía).
    load = [round(sum(r.training_load or 0.0 for r in w)) for w in weeks_all]
    return {
        "generated": generated.isoformat(),
        "count": len(rows),
        "weeks": [m.isoformat() for m in mondays],
        "totals": {
            "minutes": [_minutes(w) for w in weeks_all],
            "sessions": [len(w) for w in weeks_all],
            "calories": [round(sum(r.calories or 0.0 for r in w)) for w in weeks_all],
            "load": load,
            "load_avg4": [round(v) for v in moving_average(load, 4)],
            # Minutos en cada zona de FC, de Z1 a Z5.
            "zones": [[round(sum(r.hr_zone_seconds[z] or 0.0 for r in w) / 60) for z in range(5)] for w in weeks_all],
        },
        "vo2max": [{"date": r.date.isoformat(), "value": r.vo2max} for r in chronological if r.vo2max is not None],
        "sports": sports,
        "days": days,
        "bests": [
            {
                "label": label,
                "seconds": round(pb.time_seconds) if pb else None,
                "pace": round(pb.time_seconds / (distance_m / 1000)) if pb else None,
                "date": pb.achieved_on.isoformat() if pb else None,
                "name": pb.activity_name if pb else None,
            }
            for distance_m, label in sorted(STANDARD_DISTANCES_M.items())
            for pb in [personal_bests.get(distance_m)]
        ],
        "recent": [
            {
                "date": r.date.isoformat(),
                "sport": _sport_of(r)[0],
                "slot": _sport_of(r)[1],
                "name": r.name,
                "minutes": _minutes([r]),
                "km": _num(r.distance_km),
                "hr": r.avg_hr,
            }
            for r in recent
        ],
    }


def write_dashboard(path: Path, data: dict) -> None:
    # "</" escapado para que un nombre de actividad no pueda cerrar el <script>.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", payload), encoding="utf-8")
