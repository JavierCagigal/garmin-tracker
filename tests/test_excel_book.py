from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from garmin_tracker.activity_model import build_activity_row
from garmin_tracker.excel_book import ACTIVITIES_SHEET_NAME, write_workbook
from tests.fixtures import indoor_cycling_activity, running_activity, strength_activity


def test_write_workbook_creates_activities_sheet_with_expected_structure(tmp_path: Path) -> None:
    rows = [
        build_activity_row(running_activity()),
        build_activity_row(indoor_cycling_activity()),
        build_activity_row(strength_activity()),
    ]
    out_path = tmp_path / "entrenamientos.xlsx"

    write_workbook(rows, out_path)

    assert out_path.exists()
    wb = load_workbook(out_path)
    assert wb.sheetnames == [ACTIVITIES_SHEET_NAME]

    ws = wb[ACTIVITIES_SHEET_NAME]
    assert ws["A1"].value == "Fecha"
    assert ws["D1"].value == "Nombre"
    assert ws.cell(row=1, column=ws.max_column).value == "activityId"

    # cabecera en negrita
    assert ws["A1"].font.bold is True

    # 3 filas de datos + 1 de cabecera
    assert ws.max_row == 4

    # congelado y autofiltro activos
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == ws.dimensions

    # formato de fecha/duración correcto, no números crudos
    date_col = 1
    assert ws.cell(row=2, column=date_col).number_format == "DD/MM/YYYY"
    duration_col = 6
    assert ws.cell(row=2, column=duration_col).number_format == "[h]:mm:ss"


def test_write_workbook_is_idempotent_when_regenerated(tmp_path: Path) -> None:
    out_path = tmp_path / "entrenamientos.xlsx"
    rows = [build_activity_row(running_activity())]

    write_workbook(rows, out_path)
    write_workbook(rows, out_path)  # segunda pasada no debe duplicar hojas ni romper nada

    wb = load_workbook(out_path)
    assert wb.sheetnames == [ACTIVITIES_SHEET_NAME]
    assert wb[ACTIVITIES_SHEET_NAME].max_row == 2
