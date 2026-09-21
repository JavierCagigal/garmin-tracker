"""Hoja 'Progresión': "¿he mejorado?" — deltas semanales, ACWR, Efficiency
Factor por deporte y mejores marcas.

Formato condicional (calculado en Python al generar, no como regla viva de
Excel, porque la hoja entera se regenera en cada sync): verde = mejora,
rojo = empeora, gris = muestra demasiado pequeña o sin datos suficientes
para concluir nada.
"""

from __future__ import annotations

from datetime import date, timedelta

from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from garmin_tracker.excel_common import (
    FILL_GRAY,
    FILL_GREEN,
    FILL_RED,
    TITLE_FONT,
    apply_number_formats,
    autofit_columns,
    write_header,
)
from garmin_tracker.progression import (
    STANDARD_DISTANCES_M,
    AcwrPoint,
    EfficiencyFactorDelta,
    PersonalBest,
    WeeklyComparison,
)

SHEET_NAME = "Progresión"

_DURATION_FMT = "[h]:mm:ss"

_ACWR_STATUS_FILL = {
    "ok": FILL_GREEN,
    "alto": FILL_RED,
    "bajo": FILL_RED,
    "sin datos": FILL_GRAY,
    "historial insuficiente": FILL_GRAY,
}

_WEEKLY_COLUMNS: list[tuple[str, str | None]] = [
    ("Inicio semana (lunes)", "DD/MM/YYYY"),
    ("Año ISO", "0"),
    ("Semana ISO", "0"),
    ("Sesiones", "0"),
    ("¿Comparable?", None),
    ("Volumen (km)", "0.00"),
    ("Δ vs sem. anterior (km)", "0.00"),
    ("Δ vs sem. anterior (%)", '0.0"%"'),
    ("Δ vs media 4 sem (km)", "0.00"),
    ("Δ vs media 4 sem (%)", '0.0"%"'),
    ("Tiempo (min)", "0"),
    ("Δ vs sem. anterior (min)", "0"),
    ("Δ vs sem. anterior (%)", '0.0"%"'),
    ("Δ vs media 4 sem (min)", "0"),
    ("Δ vs media 4 sem (%)", '0.0"%"'),
    ("Carga TRIMP (UA)", "0.0"),
    ("Δ vs sem. anterior (UA)", "0.0"),
    ("Δ vs sem. anterior (%)", '0.0"%"'),
    ("Δ vs media 4 sem (UA)", "0.0"),
    ("Δ vs media 4 sem (%)", '0.0"%"'),
    ("Ritmo (min/km)", "mm:ss"),
    ("Δ ritmo vs sem. anterior", "mm:ss"),
    ("Δ ritmo vs sem. anterior (%)", '0.0"%"'),
    ("Δ ritmo vs media 4 sem", "mm:ss"),
    ("Δ ritmo vs media 4 sem (%)", '0.0"%"'),
    ("ACWR (7d/28d)", "0.00"),
    ("Estado ACWR", None),
]

_EF_COLUMNS: list[tuple[str, str | None]] = [
    ("Inicio semana (lunes)", "DD/MM/YYYY"),
    ("Año ISO", "0"),
    ("Semana ISO", "0"),
    ("Deporte", None),
    ("Sesiones", "0"),
    ("Efficiency Factor (km/h por lpm)", "0.000"),
    ("Δ vs última vez practicado", "0.000"),
    ("Δ vs última vez practicado (%)", '0.0"%"'),
]

_PB_COLUMNS: list[tuple[str, str | None]] = [
    ("Distancia", None),
    ("Tiempo", _DURATION_FMT),
    ("Ritmo (min/km)", "mm:ss"),
    ("Fecha", "DD/MM/YYYY"),
    ("Actividad", None),
    ("activityId", "0"),
]


def _delta_fill(delta: float | None, *, invert: bool = False) -> object | None:
    if delta is None or delta == 0:
        return None
    positive = delta > 0
    if invert:
        positive = not positive
    return FILL_GREEN if positive else FILL_RED


def _paint(ws: Worksheet, row: int, col: int, fill: object | None) -> None:
    if fill is not None:
        ws.cell(row=row, column=col).fill = fill


def _write_section_title(ws: Worksheet, row: int, text: str) -> None:
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = TITLE_FONT


def _write_weekly_section(ws: Worksheet, start_row: int, comparisons: list[WeeklyComparison], acwr_points: list[AcwrPoint]) -> int:
    _write_section_title(ws, start_row, "Progresión semanal (todos los deportes)")
    header_row = start_row + 1
    write_header(ws, [h for h, _fmt in _WEEKLY_COLUMNS], row=header_row)

    # comparisons y acwr_points vienen de la MISMA serie continua de semanas,
    # en el mismo orden: se pueden emparejar por posición. Se muestran de más
    # reciente a más antigua.
    paired = list(zip(comparisons, acwr_points))
    paired.reverse()

    row = header_row + 1
    for comparison, acwr in paired:
        week_start = date.fromisocalendar(comparison.iso_year, comparison.iso_week, 1)
        vol, dur, load, pace = (
            comparison.volume_km,
            comparison.duration_min,
            comparison.training_load,
            comparison.pace_min_per_km,
        )
        pace_val = timedelta(minutes=pace.value) if pace.value is not None else None
        pace_d_prev = timedelta(minutes=pace.delta_vs_prev) if pace.delta_vs_prev is not None else None
        pace_d_ma4 = timedelta(minutes=pace.delta_vs_ma4) if pace.delta_vs_ma4 is not None else None

        ws.append(
            [
                week_start,
                comparison.iso_year,
                comparison.iso_week,
                comparison.sessions,
                "Sí" if comparison.comparable else "No (< 2 sesiones)",
                vol.value,
                vol.delta_vs_prev,
                vol.pct_vs_prev,
                vol.delta_vs_ma4,
                vol.pct_vs_ma4,
                dur.value,
                dur.delta_vs_prev,
                dur.pct_vs_prev,
                dur.delta_vs_ma4,
                dur.pct_vs_ma4,
                load.value,
                load.delta_vs_prev,
                load.pct_vs_prev,
                load.delta_vs_ma4,
                load.pct_vs_ma4,
                pace_val,
                pace_d_prev,
                pace.pct_vs_prev,
                pace_d_ma4,
                pace.pct_vs_ma4,
                acwr.ratio,
                acwr.status,
            ]
        )

        comparable = comparison.comparable
        # columnas 7-10: volumen; 12-15: tiempo; 17-20: carga (más alto = verde)
        for delta_col, delta_val in ((7, vol.delta_vs_prev), (9, vol.delta_vs_ma4)):
            _paint(ws, row, delta_col, FILL_GRAY if not comparable and delta_val is not None else _delta_fill(delta_val))
        for delta_col, delta_val in ((12, dur.delta_vs_prev), (14, dur.delta_vs_ma4)):
            _paint(ws, row, delta_col, FILL_GRAY if not comparable and delta_val is not None else _delta_fill(delta_val))
        for delta_col, delta_val in ((17, load.delta_vs_prev), (19, load.delta_vs_ma4)):
            _paint(ws, row, delta_col, FILL_GRAY if not comparable and delta_val is not None else _delta_fill(delta_val))
        # columnas 22, 24: ritmo (más bajo = verde -> invert=True)
        for delta_col, delta_val in ((22, pace.delta_vs_prev), (24, pace.delta_vs_ma4)):
            _paint(
                ws, row, delta_col,
                FILL_GRAY if not comparable and delta_val is not None else _delta_fill(delta_val, invert=True),
            )
        # ACWR: columnas 26 (ratio) y 27 (estado)
        status_fill = _ACWR_STATUS_FILL.get(acwr.status)
        _paint(ws, row, 26, status_fill)
        _paint(ws, row, 27, status_fill)

        row += 1

    apply_number_formats(ws, [fmt for _h, fmt in _WEEKLY_COLUMNS], start_row=header_row + 1, end_row=row - 1)
    return row


def _write_ef_section(ws: Worksheet, start_row: int, ef_deltas: list[EfficiencyFactorDelta]) -> int:
    _write_section_title(ws, start_row, "Efficiency Factor por deporte (velocidad media / FC media)")
    header_row = start_row + 1
    write_header(ws, [h for h, _fmt in _EF_COLUMNS], row=header_row)

    # Se reordena por deporte y luego cronológicamente, para leer la
    # evolución de cada deporte de un tirón en vez de intercalada por semana.
    ordered = sorted(ef_deltas, key=lambda d: (d.sport_label, d.iso_year, d.iso_week))

    row = header_row + 1
    for d in ordered:
        week_start = date.fromisocalendar(d.iso_year, d.iso_week, 1)
        ws.append(
            [
                week_start,
                d.iso_year,
                d.iso_week,
                d.sport_label,
                d.sessions,
                d.value,
                d.delta_vs_prev_practice,
                d.pct_vs_prev_practice,
            ]
        )
        _paint(ws, row, 7, _delta_fill(d.delta_vs_prev_practice))
        _paint(ws, row, 8, _delta_fill(d.delta_vs_prev_practice))
        row += 1

    apply_number_formats(ws, [fmt for _h, fmt in _EF_COLUMNS], start_row=header_row + 1, end_row=row - 1)
    return row


def _write_personal_bests_section(ws: Worksheet, start_row: int, personal_bests: dict[int, PersonalBest]) -> int:
    _write_section_title(ws, start_row, "Mejores marcas")
    header_row = start_row + 1
    write_header(ws, [h for h, _fmt in _PB_COLUMNS], row=header_row)

    row = header_row + 1
    for distance_m in sorted(STANDARD_DISTANCES_M):
        pb = personal_bests.get(distance_m)
        if pb is None:
            ws.append([STANDARD_DISTANCES_M[distance_m], None, None, None, "Sin marca todavía", None])
        else:
            pace = timedelta(minutes=(pb.time_seconds / 60) / (pb.distance_m / 1000))
            ws.append(
                [
                    pb.distance_label,
                    timedelta(seconds=pb.time_seconds),
                    pace,
                    pb.achieved_on,
                    pb.activity_name,
                    pb.activity_id,
                ]
            )
        row += 1

    apply_number_formats(ws, [fmt for _h, fmt in _PB_COLUMNS], start_row=header_row + 1, end_row=row - 1)
    return row


def write_progression_sheet(
    wb: Workbook,
    *,
    weekly_comparisons: list[WeeklyComparison],
    acwr_points: list[AcwrPoint],
    ef_deltas: list[EfficiencyFactorDelta],
    personal_bests: dict[int, PersonalBest],
) -> None:
    if SHEET_NAME in wb.sheetnames:
        del wb[SHEET_NAME]
    ws = wb.create_sheet(SHEET_NAME)

    next_row = _write_weekly_section(ws, 1, weekly_comparisons, acwr_points)
    next_row = _write_ef_section(ws, next_row + 1, ef_deltas)
    _write_personal_bests_section(ws, next_row + 1, personal_bests)

    autofit_columns(ws)
