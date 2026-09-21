"""Gráficas NATIVAS de Excel (openpyxl.chart), no imágenes incrustadas: los
gráficos referencian celdas reales de la hoja "_ChartData", así que si se
tocan esos datos y se regenera el libro, el gráfico se actualiza solo.
"""

from __future__ import annotations

from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.workbook.workbook import Workbook

from garmin_tracker.excel_chart_data import ChartDataLayout
from garmin_tracker.progression import STANDARD_DISTANCES_M

CHARTS_SHEET_NAME = "Gráficas"


def _add_volume_chart(ws, data_ws, layout: ChartDataLayout, anchor: str) -> None:
    if layout.weekly_row_count == 0:
        return
    header_row = layout.weekly_header_row
    last_row = header_row + layout.weekly_row_count
    cats = Reference(data_ws, min_col=1, max_col=1, min_row=header_row + 1, max_row=last_row)

    bar = BarChart()
    bar.type = "col"
    bar.title = "Volumen semanal (km) y media móvil 4 semanas"
    bar.y_axis.title = "km"
    bar.x_axis.title = "Semana"
    bar.add_data(Reference(data_ws, min_col=2, max_col=2, min_row=header_row, max_row=last_row), titles_from_data=True)
    bar.set_categories(cats)

    line = LineChart()
    line.add_data(Reference(data_ws, min_col=3, max_col=3, min_row=header_row, max_row=last_row), titles_from_data=True)
    for s in line.series:
        s.marker.symbol = "none"
        s.smooth = False

    bar += line
    bar.width, bar.height = 24, 10
    ws.add_chart(bar, anchor)


def _add_efficiency_factor_chart(ws, data_ws, layout: ChartDataLayout, anchor: str) -> None:
    if layout.ef_row_count == 0 or not layout.ef_sports:
        return
    header_row = layout.ef_header_row
    last_row = header_row + layout.ef_row_count
    cats = Reference(data_ws, min_col=layout.ef_start_col, max_col=layout.ef_start_col, min_row=header_row + 1, max_row=last_row)

    chart = LineChart()
    chart.title = "Evolución del Efficiency Factor por deporte"
    chart.y_axis.title = "km/h por lpm"
    chart.x_axis.title = "Semana"
    data = Reference(
        data_ws,
        min_col=layout.ef_start_col + 1,
        max_col=layout.ef_start_col + len(layout.ef_sports),
        min_row=header_row,
        max_row=last_row,
    )
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    for s in chart.series:
        s.smooth = False
    chart.width, chart.height = 24, 10
    ws.add_chart(chart, anchor)


def _add_load_acwr_chart(ws, data_ws, layout: ChartDataLayout, anchor: str) -> None:
    if layout.weekly_row_count == 0:
        return
    header_row = layout.weekly_header_row
    last_row = header_row + layout.weekly_row_count
    cats = Reference(data_ws, min_col=1, max_col=1, min_row=header_row + 1, max_row=last_row)

    bar = BarChart()
    bar.type = "col"
    bar.title = "Carga de entrenamiento semanal y ACWR (banda recomendada 0.8-1.3)"
    bar.y_axis.title = "Carga (TRIMP, UA)"
    bar.x_axis.title = "Semana"
    bar.add_data(Reference(data_ws, min_col=4, max_col=4, min_row=header_row, max_row=last_row), titles_from_data=True)
    bar.set_categories(cats)

    line = LineChart()
    # columnas 5-7: ACWR, banda mínima (0.8), banda máxima (1.3)
    line.add_data(Reference(data_ws, min_col=5, max_col=7, min_row=header_row, max_row=last_row), titles_from_data=True)
    line.y_axis.axId = 200
    line.y_axis.title = "ACWR (ratio)"
    # OJO: la receta "oficial" de openpyxl pone `crosses='max'` en el eje
    # PRIMARIO (bar.y_axis) — probado así, en LibreOffice Calc coloca cada
    # eje en el lado correcto (izquierda/derecha) pero le asigna a cada
    # serie la escala del OTRO eje (confirmado reproduciendo el ejemplo
    # mínimo de la propia documentación de openpyxl: mismo fallo). Puesto en
    # el eje SECUNDARIO en su lugar, en LibreOffice sale correcto. No he
    # podido verificarlo contra Excel real (no hay licencia disponible); si
    # algún día lo abres con Excel y ves las escalas cambiadas, es la pista.
    line.y_axis.crosses = "max"

    styles = [("4472C4", False), ("A6A6A6", True), ("A6A6A6", True)]
    for s, (color, dashed) in zip(line.series, styles):
        s.marker.symbol = "none"
        s.smooth = False
        s.graphicalProperties.line.solidFill = color
        if dashed:
            s.graphicalProperties.line.dashStyle = "dash"
            s.graphicalProperties.line.width = 9525  # EMU (~0.75pt), línea fina de referencia

    bar += line
    bar.width, bar.height = 24, 10
    ws.add_chart(bar, anchor)


def _add_sport_distribution_chart(ws, data_ws, layout: ChartDataLayout, anchor: str) -> None:
    if layout.dist_row_count == 0:
        return
    header_row = layout.dist_header_row
    last_row = header_row + layout.dist_row_count
    labels = Reference(data_ws, min_col=layout.dist_start_col, max_col=layout.dist_start_col, min_row=header_row + 1, max_row=last_row)
    data = Reference(data_ws, min_col=layout.dist_start_col + 1, max_col=layout.dist_start_col + 1, min_row=header_row, max_row=last_row)

    pie = PieChart()
    pie.title = "Distribución de sesiones por deporte"
    pie.add_data(data, titles_from_data=True)
    pie.set_categories(labels)
    pie.width, pie.height = 14, 10
    ws.add_chart(pie, anchor)


def _add_personal_best_charts(ws, data_ws, layout: ChartDataLayout, anchor_col: str, start_row: int) -> None:
    row_cursor = start_row
    for distance_m in sorted(layout.pb_blocks):
        col, count = layout.pb_blocks[distance_m]
        if count == 0:
            continue
        header_row = layout.pb_header_row
        last_row = header_row + count
        cats = Reference(data_ws, min_col=col, max_col=col, min_row=header_row + 1, max_row=last_row)
        data = Reference(data_ws, min_col=col + 1, max_col=col + 1, min_row=header_row, max_row=last_row)

        chart = LineChart()
        chart.title = f"Progresión marca — {STANDARD_DISTANCES_M[distance_m]}"
        chart.y_axis.title = "Tiempo"
        chart.y_axis.number_format = "mm:ss" if distance_m < 10000 else "[h]:mm:ss"
        chart.x_axis.title = "Fecha"
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        for s in chart.series:
            s.marker.symbol = "circle"
            s.smooth = False
        chart.width, chart.height = 14, 9
        ws.add_chart(chart, f"{anchor_col}{row_cursor}")
        row_cursor += 19


def add_all_charts(wb: Workbook, layout: ChartDataLayout) -> None:
    if CHARTS_SHEET_NAME in wb.sheetnames:
        del wb[CHARTS_SHEET_NAME]
    ws = wb.create_sheet(CHARTS_SHEET_NAME)
    data_ws = wb[layout.sheet_name]

    _add_volume_chart(ws, data_ws, layout, "B2")
    _add_efficiency_factor_chart(ws, data_ws, layout, "B22")
    _add_load_acwr_chart(ws, data_ws, layout, "B42")
    _add_sport_distribution_chart(ws, data_ws, layout, "S2")
    _add_personal_best_charts(ws, data_ws, layout, anchor_col="S", start_row=22)
