from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from garmin_tracker.activity_model import build_activity_row
from garmin_tracker.progression import current_personal_bests
from garmin_tracker.web import build_dashboard_data, write_dashboard
from tests.fixtures import activity


def _data() -> dict:
    rows = [build_activity_row(r) for r in [
        activity(1, "2026-08-04 08:00:00", sport="lap_swimming", distance_m=400, duration_s=480),
        activity(2, "2026-08-06 08:00:00", sport="lap_swimming", distance_m=600, duration_s=840),
        # semana del 10/08: descanso
        activity(3, "2026-08-18 08:00:00", sport="treadmill_running", distance_m=10000, duration_s=3000,
                 name="Cinta </script><b>"),
    ]]
    return build_dashboard_data(rows, current_personal_bests(rows), date(2026, 8, 20))


def test_same_weekly_numbers_as_excel() -> None:
    data = _data()
    assert data["weeks"] == ["2026-08-03", "2026-08-10", "2026-08-17"]  # incluye el descanso
    assert data["totals"]["sessions"] == [2, 0, 1]
    swim = next(s for s in data["sports"] if s["name"] == "Natación")
    metrics = {m["name"]: m["values"] for m in swim["metrics"]}
    assert metrics["Metros"] == [1000, None, None]
    assert metrics["Ritmo /100 m"][0] == 132  # 2:12 ponderado, como en el Excel
    run = next(s for s in data["sports"] if s["name"] == "Correr")
    assert run["sessions"][0]["pace"] == 300  # la cinta cuenta como Correr: 5:00 /km


def test_written_html_embeds_data_safely(tmp_path: Path) -> None:
    out = tmp_path / "entrenamientos.html"
    write_dashboard(out, _data())
    html = out.read_text(encoding="utf-8")
    assert "__DATA__" not in html
    assert html.count("</script>") == 3  # el nombre de la actividad no cierra ningún <script>
    payload = html.split('<script id="data" type="application/json">')[1].split("</script>")[0]
    assert json.loads(payload)["recent"][0]["name"] == "Cinta </script><b>"
