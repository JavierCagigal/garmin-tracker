"""Generación del libro Excel (.xlsx) completo: orquesta las hojas
Actividades, Semanal y Progresión sobre el mismo Workbook.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.workbook.workbook import Workbook as WorkbookType
from openpyxl.worksheet.worksheet import Worksheet

from garmin_tracker.activity_model import ActivityRow
from garmin_tracker.aggregates import WeeklyAggregate
from garmin_tracker.excel_chart_data import write_chart_data_sheet
from garmin_tracker.excel_charts import add_all_charts
from garmin_tracker.excel_common import HEADER_FONT, save_workbook_atomic
from garmin_tracker.excel_notes import read_existing_notes, write_notes_sheet
from garmin_tracker.excel_progression import write_progression_sheet
from garmin_tracker.excel_weekly import write_weekly_sheet
from garmin_tracker.progression import (
    AcwrPoint,
    EfficiencyFactorDelta,
    PersonalBest,
    WeeklyComparison,
)

ACTIVITIES_SHEET_NAME = "Actividades"

# (cabecera, ancho de columna, formato numérico o None para texto)
_DURATION_FMT = "[h]:mm:ss"
_COLUMNS: list[tuple[str, int, str | None]] = [
    ("Fecha", 12, "DD/MM/YYYY"),
    ("Hora inicio", 11, "HH:MM:SS"),
    ("Deporte", 20, None),
    ("Nombre", 32, None),
    ("Distancia (km)", 14, "0.00"),
    ("Tiempo total", 12, _DURATION_FMT),
    ("Tiempo en movimiento", 19, _DURATION_FMT),
    ("Ritmo medio (min/km)", 18, "mm:ss"),
    ("Velocidad media (km/h)", 19, "0.0"),
    ("FC media", 10, "0"),
    ("FC máx", 10, "0"),
    ("Desnivel + (m)", 14, "0"),
    ("Calorías", 10, "0"),
    ("Cadencia media", 14, "0.0"),
    ("Potencia media (W)", 16, "0"),
    ("TE aeróbico", 12, "0.0"),
    ("TE anaeróbico", 13, "0.0"),
    ("VO2max", 10, "0.0"),
    ("FC Zona 1", 11, _DURATION_FMT),
    ("FC Zona 2", 11, _DURATION_FMT),
    ("FC Zona 3", 11, _DURATION_FMT),
    ("FC Zona 4", 11, _DURATION_FMT),
    ("FC Zona 5", 11, _DURATION_FMT),
    ("Temp mín (°C)", 13, "0.0"),
    ("Temp máx (°C)", 13, "0.0"),
    ("activityId", 16, "0"),
]


def _row_values(row: ActivityRow) -> list[object]:
    pace_value = timedelta(minutes=row.avg_pace_min_per_km) if row.avg_pace_min_per_km is not None else None
    zone_values = [timedelta(seconds=z) if z is not None else None for z in row.hr_zone_seconds]

    return [
        row.date,
        row.start_time,
        row.sport_label,
        row.name,
        row.distance_km,
        row.duration,
        row.moving_duration,
        pace_value,
        row.avg_speed_kmh,
        row.avg_hr,
        row.max_hr,
        row.elevation_gain_m,
        row.calories,
        row.avg_cadence,
        row.avg_power,
        row.aerobic_te,
        row.anaerobic_te,
        row.vo2max,
        *zone_values,
        row.temp_min_c,
        row.temp_max_c,
        row.activity_id,
    ]


def write_activities_sheet(wb: WorkbookType, rows: list[ActivityRow]) -> Worksheet:
    if ACTIVITIES_SHEET_NAME in wb.sheetnames:
        del wb[ACTIVITIES_SHEET_NAME]
    ws = wb.create_sheet(ACTIVITIES_SHEET_NAME, 0)

    headers = [header for header, _width, _fmt in _COLUMNS]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = HEADER_FONT

    for row in rows:
        ws.append(_row_values(row))

    for col_index, (_header, width, number_format) in enumerate(_COLUMNS, start=1):
        letter = get_column_letter(col_index)
        ws.column_dimensions[letter].width = width
        if number_format:
            for data_row in range(2, ws.max_row + 1):
                ws.cell(row=data_row, column=col_index).number_format = number_format

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def write_workbook(
    path: Path,
    *,
    activity_rows: list[ActivityRow],
    weekly_aggregates: list[WeeklyAggregate],
    continuous_totals: list[WeeklyAggregate],
    weekly_comparisons: list[WeeklyComparison],
    acwr_points: list[AcwrPoint],
    ef_deltas: list[EfficiencyFactorDelta],
    personal_bests: dict[int, PersonalBest],
    personal_best_history: dict[int, list[PersonalBest]],
) -> None:
    # CRÍTICO: leer las notas manuales del Excel anterior ANTES de tocar
    # nada. El fichero original en `path` no se escribe en ningún momento
    # hasta el guardado atómico final, así que si esta lectura falla (fichero
    # corrupto) la excepción aborta toda la función sin haber arriesgado el
    # original.
    existing_notes = read_existing_notes(path)

    wb = Workbook()
    wb.remove(wb.active)  # Workbook() crea una hoja "Sheet" vacía por defecto

    write_activities_sheet(wb, activity_rows)
    write_weekly_sheet(wb, weekly_aggregates)
    write_progression_sheet(
        wb,
        weekly_comparisons=weekly_comparisons,
        acwr_points=acwr_points,
        ef_deltas=ef_deltas,
        personal_bests=personal_bests,
    )
    write_notes_sheet(wb, activity_rows, existing_notes)

    layout = write_chart_data_sheet(
        wb,
        activity_rows=activity_rows,
        continuous_totals=continuous_totals,
        acwr_points=acwr_points,
        weekly_aggregates=weekly_aggregates,
        personal_best_history=personal_best_history,
    )
    add_all_charts(wb, layout)

    save_workbook_atomic(wb, path)
