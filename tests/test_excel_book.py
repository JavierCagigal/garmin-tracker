from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from garmin_tracker.activity_model import build_activity_row
from garmin_tracker.aggregates import aggregate_by_week
from garmin_tracker.excel_book import ACTIVITIES_SHEET_NAME, write_workbook
from garmin_tracker.excel_progression import SHEET_NAME as PROGRESSION_SHEET_NAME
from garmin_tracker.excel_weekly import SHEET_NAME as WEEKLY_SHEET_NAME
from garmin_tracker.progression import (
    acwr_series,
    compute_weekly_deltas,
    continuous_weekly_totals,
    current_personal_bests,
    efficiency_factor_deltas,
)
from tests.fixtures import indoor_cycling_activity, running_activity, strength_activity


def _write(rows, out_path: Path) -> None:
    """Reproduce el mismo pipeline que scripts/generate_excel.py, para no
    duplicar la orquestación en cada test."""
    weekly_aggregates = aggregate_by_week(rows)
    continuous_totals = continuous_weekly_totals(rows)
    write_workbook(
        out_path,
        activity_rows=rows,
        weekly_aggregates=weekly_aggregates,
        weekly_comparisons=compute_weekly_deltas(continuous_totals),
        acwr_points=acwr_series(rows, continuous_totals),
        ef_deltas=efficiency_factor_deltas(weekly_aggregates),
        personal_bests=current_personal_bests(rows),
    )


def test_write_workbook_creates_all_three_sheets(tmp_path: Path) -> None:
    rows = [
        build_activity_row(running_activity()),
        build_activity_row(indoor_cycling_activity()),
        build_activity_row(strength_activity()),
    ]
    out_path = tmp_path / "entrenamientos.xlsx"

    _write(rows, out_path)

    assert out_path.exists()
    wb = load_workbook(out_path)
    assert wb.sheetnames == [ACTIVITIES_SHEET_NAME, WEEKLY_SHEET_NAME, PROGRESSION_SHEET_NAME]


def test_activities_sheet_structure(tmp_path: Path) -> None:
    rows = [
        build_activity_row(running_activity()),
        build_activity_row(indoor_cycling_activity()),
        build_activity_row(strength_activity()),
    ]
    out_path = tmp_path / "entrenamientos.xlsx"
    _write(rows, out_path)

    ws = load_workbook(out_path)[ACTIVITIES_SHEET_NAME]
    assert ws["A1"].value == "Fecha"
    assert ws["D1"].value == "Nombre"
    assert ws.cell(row=1, column=ws.max_column).value == "activityId"
    assert ws["A1"].font.bold is True
    assert ws.max_row == 4  # 3 filas de datos + cabecera

    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == ws.dimensions

    date_col, duration_col = 1, 6
    assert ws.cell(row=2, column=date_col).number_format == "DD/MM/YYYY"
    assert ws.cell(row=2, column=duration_col).number_format == "[h]:mm:ss"


def test_weekly_sheet_has_total_and_sport_rows(tmp_path: Path) -> None:
    rows = [
        build_activity_row(running_activity()),
        build_activity_row(strength_activity()),
    ]
    out_path = tmp_path / "entrenamientos.xlsx"
    _write(rows, out_path)

    ws = load_workbook(out_path)[WEEKLY_SHEET_NAME]
    assert ws["A1"].value == "Inicio semana (lunes)"
    sport_column_values = [ws.cell(row=r, column=4).value for r in range(2, ws.max_row + 1)]
    assert "Total" in sport_column_values
    assert ws.freeze_panes == "A2"


def test_progression_sheet_has_three_sections(tmp_path: Path) -> None:
    rows = [build_activity_row(running_activity())]
    out_path = tmp_path / "entrenamientos.xlsx"
    _write(rows, out_path)

    ws = load_workbook(out_path)[PROGRESSION_SHEET_NAME]
    titles = [cell.value for row in ws.iter_rows(min_col=1, max_col=1) for cell in row if cell.value]
    assert "Progresión semanal (todos los deportes)" in titles
    assert "Efficiency Factor por deporte (velocidad media / FC media)" in titles
    assert "Mejores marcas" in titles


def test_write_workbook_is_idempotent_when_regenerated(tmp_path: Path) -> None:
    rows = [build_activity_row(running_activity())]
    out_path = tmp_path / "entrenamientos.xlsx"

    _write(rows, out_path)
    _write(rows, out_path)  # segunda pasada no debe duplicar hojas ni romper nada

    wb = load_workbook(out_path)
    assert wb.sheetnames == [ACTIVITIES_SHEET_NAME, WEEKLY_SHEET_NAME, PROGRESSION_SHEET_NAME]
    assert wb[ACTIVITIES_SHEET_NAME].max_row == 2
