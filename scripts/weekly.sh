#!/bin/sh
# Job semanal (launchd, lunes 07:00): Garmin -> SQLite -> Excel + web, y publica
# la web en GitHub Pages (docs/index.html en master).
set -e
cd "$(dirname "$0")/.."

./.venv/bin/python scripts/sync.py
./.venv/bin/python scripts/generate_excel.py
./.venv/bin/python scripts/generate_web.py

# Solo se commitea docs/index.html, aunque haya otros cambios a medias, y solo
# en master: si estás trabajando en otra rama, esa semana no se publica.
if [ "$(git branch --show-current)" != master ]; then
  echo "No estoy en master: la web no se publica esta semana."
  exit 0
fi
mkdir -p docs
cp output/entrenamientos.html docs/index.html
git add docs/index.html
git diff --cached --quiet -- docs/index.html && exit 0
git commit -q -m "Web: datos actualizados el $(date +%d/%m/%Y)" -- docs/index.html
git push -q origin master
echo "Web publicada."
