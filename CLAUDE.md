# garmin-tracker

Descarga las actividades de Garmin Connect a una caché SQLite y genera un Excel
(`output/entrenamientos.xlsx`) para seguir la progresión de los entrenamientos.
Proyecto personal. Se responde en español.

## Dónde corre

- **Mac** (macOS). El usuario abre el Excel con **Numbers**, no con Excel ni con
  LibreOffice. Todo lo visual se valida en Numbers (ver "Peculiaridades de Numbers").
- Python 3.14 con venv en `.venv/`; para montarlo: `python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt`.
- Credenciales en `.env` (gitignored). La sesión OAuth de Garmin se guarda en
  `~/.garminconnect`; si se pierde (p. ej. al formatear), la primera ejecución
  de `sync.py` pide el login y puede pedir código MFA: debe lanzarla el usuario
  en su propia terminal, no Claude.

## Comandos

```bash
./.venv/bin/python scripts/sync.py            # descarga incremental desde Garmin
./.venv/bin/python scripts/generate_excel.py  # regenera el Excel desde SQLite
./.venv/bin/python scripts/generate_web.py    # regenera el panel web desde SQLite
./.venv/bin/python -m pytest -q               # tests
```

## Automatización semanal (launchd, no systemd)

`launchd/com.javiercagigal.garmin-tracker.plist` hace sync + Excel + web **los
lunes a las 07:00**. Instalado en `~/Library/LaunchAgents/`. Tras formatear:

```bash
mkdir -p ~/Library/LaunchAgents && cp launchd/*.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.javiercagigal.garmin-tracker.plist
launchctl kickstart gui/$(id -u)/com.javiercagigal.garmin-tracker   # ejecutar ya
tail ~/garmin-tracker/logs/launchd.log
```

`systemd/` y la sección de systemd/cron del README son de la versión original
para Linux; en este Mac no se usan.

## El Excel (se regenera entero en cada ejecución)

Orden de pestañas: Actividades · Semanal · Progresión · Correr · Natación ·
Ciclismo · Fuerza · Notas.

- **Actividades**: una fila por entreno (más reciente arriba).
- **Semanal**: agregados por semana ISO, TOTAL + una fila por deporte.
- **Progresión** (`excel_progression.py`): un bloque por deporte, uno debajo de
  otro, **sesión a sesión** en orden cronológico, ≤ 8 columnas, columna Fecha
  fija. Correr y Natación comparan el ritmo con la sesión anterior y con la
  media de las 4 anteriores (`progression.pace_deltas`); verde = más rápido.
  Debajo de Correr, las mejores marcas. Caminar no aparece.
- **Correr / Natación / Ciclismo / Fuerza** (`excel_charts.py`): tabla semanal
  (lunes a domingo, incluidas las semanas de descanso, como filas vacías) y
  gráficas nativas que leen esa tabla. Cada título lleva el deporte y el valor
  de la última semana. La definición de cada deporte y sus métricas está en
  `excel_charts.SPORTS`, que también usa Progresión.
- **Notas**: columnas manuales del usuario, que se **conservan** entre
  regeneraciones (se fusionan por activityId). Cualquier otra edición manual se pierde.

## El panel web (`output/entrenamientos.html`, gitignored)

Página estática, más visual que el Excel, con el estilo de un dashboard blanco
(tarjetas con sparklines, selector 4/8/12 sem/Todo). Generada por `web.py` a
partir de la plantilla `web_template.html`, con los datos incrustados como JSON:
se abre con doble clic. Reutiliza `excel_charts.SPORTS` y `weekly_buckets`, así
que las cifras coinciden con el Excel. Usa Chart.js desde cdnjs (hace falta
internet) y respeta el modo claro/oscuro del sistema. No lleva coordenadas GPS.
No se usa doble eje: el ritmo va en su propia gráfica y la FC sale en el tooltip.
Colores elegidos por el usuario: Correr rojo, Natación azul, Ciclismo verde agua,
Fuerza amarillo; violeta = todos los deportes juntos (totales, calendario, zonas, carga).
Secciones: KPIs de la última semana (+ VO2máx), resumen del periodo elegido,
tiempo semanal por deporte + constancia, zonas de FC + carga (TRIMP, media 4 sem),
panel por deporte, hábitos (día de la semana y hora), mejores marcas, récords
históricos y últimas actividades.
Pendiente: publicarla en GitHub Pages. El repo es privado y Pages siempre es
público; está sin decidir si se hace público o se usa un repo aparte.

## Decisiones tomadas con el usuario

- Correr + cinta + pista = una sola categoría "Correr"
  (`activity_model.SPORT_GROUPS`). En el Excel ya no se distinguen; el tipo
  original sigue en SQLite y suele verse en el nombre de la actividad.
- Ciclismo se mide en **minutos**, no en km: casi todo es rodillo (0 km).
- Ritmo = tiempo en movimiento total / distancia total (ponderado), nunca la media de los ritmos.
- Se quitaron, por resultar confusos: Efficiency Factor, ACWR, la tabla
  semanal de todos los deportes mezclados, el gráfico de tarta y la hoja
  oculta `_ChartData`.

## Peculiaridades de Numbers (aprendidas probando)

- Formatos de fecha y hora en **minúsculas** (`dd/mm/yyyy`, `hh:mm:ss`): con
  mayúsculas, Numbers muestra "DD" y "YYYY" literalmente.
- Duraciones con `h:mm:ss`, **no** `[h]:mm:ss`: Numbers lo muestra mal.
  Además, las duraciones se redondean al segundo en `build_activity_row`.
- Las diferencias de ritmo van en segundos con formato de una sola sección
  (`0" s"`): un formato `+0;-0` hace que Numbers muestre el signo dos veces
  ("--32 s"), y un tiempo negativo se muestra como una fecha absurda.
- Gráficas de openpyxl: hay que poner `x_axis.delete = False` /
  `y_axis.delete = False`, o los ejes no se ven. Las etiquetas de datos con
  todos los `show*` explícitos.
- Para revisar visualmente: dejar solo la pestaña en una copia del xlsx,
  exportarla a PDF con
  `osascript` → `tell application "Numbers Creator Studio"` → `export … as PDF`,
  convertir con `sips -s format png` y leer el PNG.

## Estado / pendiente

- Histórico en Garmin desde el 22/08/2026 (es todo lo que devuelve la cuenta).
- Partes del README están desactualizadas: las secciones "Progresión",
  "Gráficas" y la automatización describen la versión anterior. Fuente de verdad: este fichero.
- Ideas que se le ofrecieron al usuario y no ha pedido todavía:
  - unificar Ciclismo y Ciclismo indoor en Semanal;
  - una métrica de progresión para Ciclismo y Fuerza (p. ej. carga);
  - excluir las sesiones de correr muy lentas o cortas de la gráfica de ritmo.
- Bici estática del gimnasio: registra 0 km. El usuario va a averiguar la
  marca y el modelo para ver si emite datos por Bluetooth FTMS o ANT+ FE-C y
  se puede vincular como sensor al Garmin. Su NFC es para Apple Watch
  (GymKit) y no sirve con Garmin. Hasta entonces, Ciclismo se queda en
  minutos y FC. Si empieza a haber km o potencia, añadirlos a
  `excel_charts.SPORTS` (Ciclismo).
