"""Una pestaña por deporte (Correr, Natación, Ciclismo, Fuerza): a la
izquierda una tabla semanal (lunes a domingo, todo el histórico, incluidas
las semanas de descanso para que el eje de tiempo sea continuo) y a la
derecha sus gráficas NATIVAS (openpyxl.chart, no imágenes), que leen
directamente esa tabla.

Cada título lleva el deporte y el valor de la última semana con datos
("Natación · Ritmo /100 m · última semana: 2:20"), para que nunca haya
duda de a qué modalidad pertenece una gráfica.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.workbook.workbook import Workbook

from garmin_tracker.activity_model import ActivityRow
from garmin_tracker.excel_common import TITLE_FONT, autofit_columns, write_header


def _km(rows: list[ActivityRow]) -> float:
    return sum(r.distance_km or 0.0 for r in rows)


def _minutes(rows: list[ActivityRow]) -> float:
    return sum(r.duration.total_seconds() for r in rows) / 60


def _pace(rows: list[ActivityRow], per_m: int) -> timedelta | None:
    """Ritmo ponderado: tiempo en movimiento total / distancia total, por
    `per_m` metros (no la media de los ritmos de cada sesión)."""
    with_distance = [r for r in rows if r.distance_km]
    km = _km(with_distance)
    if not km:
        return None
    seconds = sum((r.moving_duration or r.duration).total_seconds() for r in with_distance)
    return timedelta(seconds=seconds / (km * 1000) * per_m)


def _avg_hr(rows: list[ActivityRow]) -> float | None:
    pairs = [(r.avg_hr, r.duration.total_seconds()) for r in rows if r.avg_hr]
    total = sum(s for _, s in pairs)
    return sum(hr * s for hr, s in pairs) / total if total else None


@dataclass(frozen=True)
class _Metric:
    name: str
    unit: str  # para el título; "" si no aplica
    compute: Callable[[list[ActivityRow]], float | timedelta | None]
    number_format: str
    chart: str | None  # "bar", "line" o None (solo en la tabla)


@dataclass(frozen=True)
class _Sport:
    name: str  # también es el nombre de la pestaña
    keys: frozenset[str]
    metrics: list[_Metric]


_SESSIONS = _Metric("Sesiones", "", len, "0", None)
_HR = _Metric("FC media (lpm)", "lpm", _avg_hr, "0", "line")

SPORTS = [
    _Sport("Correr", frozenset({"running", "trail_running"}), [
        _SESSIONS,
        _Metric("Km", "km", _km, "0.0", "bar"),
        _Metric("Ritmo /km", "/km", lambda rs: _pace(rs, 1000), "m:ss", "line"),
        _HR,
    ]),
    _Sport("Natación", frozenset({"lap_swimming", "open_water_swimming"}), [
        _SESSIONS,
        _Metric("Metros", "m", lambda rs: _km(rs) * 1000, "#,##0", "bar"),
        _Metric("Ritmo /100 m", "/100 m", lambda rs: _pace(rs, 100), "m:ss", "line"),
        _HR,
    ]),
    # Casi todo es rodillo (0 km), así que el volumen va en minutos, no en km.
    _Sport("Ciclismo", frozenset({"cycling", "indoor_cycling", "road_biking", "mountain_biking", "gravel_cycling"}), [
        _SESSIONS,
        _Metric("Minutos", "min", _minutes, "0", "bar"),
        _HR,
    ]),
    _Sport("Fuerza", frozenset({"strength_training"}), [
        _Metric("Sesiones", "", len, "0", "bar"),
        _Metric("Minutos", "min", _minutes, "0", "bar"),
        _HR,
    ]),
]
SPORT_SHEET_NAMES = [s.name for s in SPORTS]

_TABLE_HEADER_ROW = 3
_PACE_HINT = " (menos es mejor)"


def _format(value: float | timedelta, number_format: str) -> str:
    if isinstance(value, timedelta):
        minutes, seconds = divmod(round(value.total_seconds()), 60)
        return f"{minutes}:{seconds:02d}"
    if number_format == "0.0":
        return f"{value:.1f}".replace(".", ",")
    return f"{round(value):,}".replace(",", ".")


def _labels(number_format: str) -> DataLabelList:
    # Los show* a False explícitos: si faltan, Excel pinta también el nombre
    # de la serie y la categoría en cada etiqueta.
    return DataLabelList(
        numFmt=number_format, showVal=True,
        showSerName=False, showCatName=False, showLegendKey=False, showPercent=False,
    )


def _chart(kind: str, title: str, number_format: str):
    chart = BarChart() if kind == "bar" else LineChart()
    chart.title = title
    chart.legend = None
    chart.dataLabels = _labels(number_format)
    chart.y_axis.number_format = number_format
    chart.y_axis.majorGridlines = None
    # openpyxl 3.1 deja los ejes sin `delete=0` y Excel/Numbers recientes
    # los ocultan: hay que decirlo explícitamente.
    chart.x_axis.delete = False
    chart.y_axis.delete = False
    chart.width, chart.height = 20, 7.5
    if kind == "bar":
        chart.type = "col"
        chart.gapWidth = 30  # columnas pegadas (por defecto 150)
    return chart


def weekly_buckets(rows: list[ActivityRow]) -> tuple[list[date], dict[date, list[ActivityRow]]]:
    """Lunes de todas las semanas entre la primera y la última actividad
    (incluidas las de descanso) y las actividades de cada una. `rows` no vacío."""
    by_week: dict[date, list[ActivityRow]] = defaultdict(list)
    for r in rows:
        by_week[r.date - timedelta(days=r.date.weekday())].append(r)
    first, last = min(by_week), max(by_week)
    return [first + timedelta(weeks=i) for i in range((last - first).days // 7 + 1)], by_week


def add_sport_sheets(wb: Workbook, rows: list[ActivityRow]) -> None:
    if not rows:
        return
    # Mismo eje de semanas en todas las pestañas, para poder compararlas.
    mondays, by_week = weekly_buckets(rows)

    for sport in SPORTS:
        weeks = [[r for r in by_week.get(m, []) if r.sport_key in sport.keys] for m in mondays]
        if not any(weeks):
            continue
        latest = max(i for i, w in enumerate(weeks) if w)

        ws = wb.create_sheet(sport.name)
        write_header(ws, ["Semana (lunes)"] + [m.name for m in sport.metrics], row=_TABLE_HEADER_ROW)
        first_row = _TABLE_HEADER_ROW + 1
        last_row = first_row + len(mondays) - 1
        for i, (monday, week_rows) in enumerate(zip(mondays, weeks)):
            # "d mmm" (17 ago) y no dd/mm/yyyy: el eje de las gráficas toma
            # este formato y con la fecha completa se salta semanas.
            ws.cell(row=first_row + i, column=1, value=monday).number_format = "d mmm yy"
            if not week_rows:
                continue
            for col, metric in enumerate(sport.metrics, start=2):
                ws.cell(row=first_row + i, column=col, value=metric.compute(week_rows)).number_format = metric.number_format
        autofit_columns(ws)
        # El título va después del autoajuste para no ensanchar la columna A.
        ws.cell(row=1, column=1, value=f"{sport.name} — resumen semanal (lunes a domingo; fila vacía = semana sin {sport.name.lower()})").font = TITLE_FONT

        cats = Reference(ws, min_col=1, min_row=first_row, max_row=last_row)
        anchor_col = len(sport.metrics) + 3  # una columna libre tras la tabla
        chart_row = _TABLE_HEADER_ROW
        for col, metric in enumerate(sport.metrics, start=2):
            if metric.chart is None:
                continue
            latest_value = metric.compute(weeks[latest])
            if latest_value is None and all(metric.compute(w) is None for w in weeks if w):
                continue  # p. ej. sin datos de FC en ningún entreno
            is_pace = metric.number_format == "m:ss"
            unit = "" if is_pace else metric.unit  # el /km ya va en el nombre
            summary = f"{_format(latest_value, metric.number_format)} {unit}".rstrip() if latest_value is not None else "sin datos"
            hint = _PACE_HINT if is_pace else ""
            chart = _chart(metric.chart, f"{sport.name} · {metric.name}{hint} · última semana: {summary}", metric.number_format)
            chart.add_data(Reference(ws, min_col=col, min_row=_TABLE_HEADER_ROW, max_row=last_row), titles_from_data=True)
            chart.set_categories(cats)
            if metric.chart == "line":
                for s in chart.series:
                    s.marker.symbol = "circle"
                    s.smooth = False
            ws.add_chart(chart, f"{ws.cell(row=1, column=anchor_col).column_letter}{chart_row}")
            chart_row += 19  # alto del gráfico + margen (Numbers usa filas más altas)
