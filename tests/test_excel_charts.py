from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook
from openpyxl.chart import BarChart, LineChart, PieChart

from garmin_tracker.activity_model import build_activity_row
from garmin_tracker.aggregates import aggregate_by_week
from garmin_tracker.excel_book import write_workbook
from garmin_tracker.excel_charts import CHARTS_SHEET_NAME
from garmin_tracker.progression import (
    acwr_series,
    compute_weekly_deltas,
    continuous_weekly_totals,
    current_personal_bests,
    efficiency_factor_deltas,
)
from garmin_tracker.progression import personal_best_history as compute_personal_best_history
from tests.fixtures import activity


def _build_multi_week_rows() -> list:
    raws = [
        activity(1, "2026-08-03 08:00:00", sport="running", distance_m=5000, duration_s=1500, fastestSplit_5000=1500.0),
        activity(2, "2026-08-10 08:00:00", sport="running", distance_m=5000, duration_s=1480, fastestSplit_5000=1480.0),
        activity(3, "2026-08-17 08:00:00", sport="cycling", distance_m=20000, duration_s=3600),
        activity(4, "2026-08-24 08:00:00", sport="running", distance_m=5000, duration_s=1450, fastestSplit_5000=1450.0),
    ]
    return [build_activity_row(r) for r in raws]


def _write(rows, out_path: Path) -> None:
    weekly_aggregates = aggregate_by_week(rows)
    continuous_totals = continuous_weekly_totals(rows)
    write_workbook(
        out_path,
        activity_rows=rows,
        weekly_aggregates=weekly_aggregates,
        continuous_totals=continuous_totals,
        weekly_comparisons=compute_weekly_deltas(continuous_totals),
        acwr_points=acwr_series(rows, continuous_totals),
        ef_deltas=efficiency_factor_deltas(weekly_aggregates),
        personal_bests=current_personal_bests(rows),
        personal_best_history=compute_personal_best_history(rows),
    )


def test_charts_sheet_contains_native_chart_objects_not_images(tmp_path: Path) -> None:
    out_path = tmp_path / "entrenamientos.xlsx"
    _write(_build_multi_week_rows(), out_path)

    wb = load_workbook(out_path)
    ws = wb[CHARTS_SHEET_NAME]

    # openpyxl expone los gráficos nativos en ws._charts (no hay imágenes de
    # matplotlib incrustadas: ws._images debe seguir vacío).
    assert len(ws._charts) >= 4
    assert ws._images == []

    assert any(isinstance(c, BarChart) for c in ws._charts)
    assert any(isinstance(c, LineChart) for c in ws._charts)
    assert any(isinstance(c, PieChart) for c in ws._charts)


def test_volume_and_load_charts_are_combo_with_two_axes(tmp_path: Path) -> None:
    out_path = tmp_path / "entrenamientos.xlsx"
    _write(_build_multi_week_rows(), out_path)

    ws = load_workbook(out_path)[CHARTS_SHEET_NAME]
    bar_charts = [c for c in ws._charts if isinstance(c, BarChart)]
    assert len(bar_charts) == 2  # volumen+media móvil, carga+ACWR

    for chart in bar_charts:
        # combo chart real: el propio openpyxl guarda [barra, línea] en _charts
        assert len(chart._charts) == 2
        assert isinstance(chart._charts[1], LineChart)

    # add_all_charts añade primero el de volumen y luego el de carga+ACWR.
    load_acwr_chart = bar_charts[1]
    acwr_line = load_acwr_chart._charts[1]
    assert acwr_line.y_axis.axId == 200  # eje secundario para no aplastar la escala de la carga
    assert len(acwr_line.series) == 3  # ACWR + banda mínima + banda máxima


def test_no_charts_sheet_data_leaks_when_no_activities(tmp_path: Path) -> None:
    out_path = tmp_path / "entrenamientos.xlsx"
    _write([], out_path)

    wb = load_workbook(out_path)
    ws = wb[CHARTS_SHEET_NAME]
    assert ws._charts == []  # sin datos, no se generan gráficos rotos vacíos
