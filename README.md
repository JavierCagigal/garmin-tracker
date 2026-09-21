# garmin-tracker

Descarga tus actividades de Garmin Connect, las cachea en SQLite (JSON crudo,
sin filtrar) y genera un Excel (`.xlsx`) con datos crudos, agregados
semanales, comparativas de progresión y gráficas nativas. Pensado para correr
en Linux, manual o por `systemd timer`/`cron`.

Compatible con **LibreOffice Calc** (no requiere Microsoft Excel): todas las
gráficas son objetos `openpyxl.chart` nativos del formato `.xlsx`, no
imágenes incrustadas.

## Instalación

Requiere Python 3.12+.

```bash
git clone <este-repo> garmin-tracker   # o usa el directorio ya clonado
cd garmin-tracker
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

> Se usa `venv` + `pip` estándar en vez de `uv`: es lo que ya trae Python, no
> añade una dependencia de sistema nueva, y para un proyecto de este tamaño
> no hay ganancia real de velocidad que lo justifique. Si prefieres `uv`,
> `uv venv && uv pip install -r requirements.txt` funciona igual de bien.

Copia `.env.example` a `.env` y rellena tus credenciales de Garmin Connect
(cuenta con usuario/contraseña propios de Garmin, no login social de
Google/Apple/Facebook):

```bash
cp .env.example .env
$EDITOR .env
```

```ini
GARMIN_EMAIL=tu_email@ejemplo.com
GARMIN_PASSWORD=tu_password
GARMIN_TOKENSTORE=~/.garminconnect       # caché de sesión OAuth, no vuelve a pedir credenciales
GARMIN_DB_PATH=./data/garmin_cache.db
GARMIN_EXCEL_PATH=./output/entrenamientos.xlsx
```

`.env` está en `.gitignore` desde el primer commit — nunca se sube a git.

## Uso

### 1. Sincronizar (descarga incremental)

```bash
./.venv/bin/python scripts/sync.py                    # incremental (por defecto)
./.venv/bin/python scripts/sync.py --full              # rehace todo el histórico
./.venv/bin/python scripts/sync.py --desde 2026-01-01   # desde una fecha concreta
./.venv/bin/python scripts/sync.py --dry-run            # simula, no escribe nada
```

La primera vez descarga todo el histórico disponible. Las siguientes solo
piden lo nuevo: pagina desde la actividad más reciente y para en cuanto
encuentra un `activityId` que ya está en caché.

Si tu cuenta tiene verificación en dos pasos (MFA), la primera ejecución
pedirá el código por terminal — necesita una sesión interactiva. Las
siguientes reutilizan el token guardado en `GARMIN_TOKENSTORE` y no vuelven
a pedir nada, salvo que ese token caduque o lo revoques desde Garmin.

### 2. Generar el Excel

```bash
./.venv/bin/python scripts/generate_excel.py
```

Lee la caché SQLite entera y regenera `output/entrenamientos.xlsx` de cero
— **excepto** la hoja "Notas", cuyas columnas manuales se leen del fichero
anterior y se fusionan (ver más abajo). La escritura es atómica: se escribe
primero a un fichero temporal junto al definitivo y solo se sustituye si
todo el proceso termina sin errores, así que un fallo a mitad de la
generación nunca deja el Excel corrupto o a medias.

### Logs

Cada ejecución escribe a `logs/garmin_tracker.log` (con rotación, 5 ficheros
de 5MB) además de a la terminal.

## Qué hay en el Excel

### Actividades
Una fila por entreno, más reciente arriba. Todos los campos que devuelve
Garmin que hemos podido mapear con sentido; celda vacía cuando el dato no
existe para esa actividad (nunca se inventa ni se aproxima).

### Semanal
Agregados por semana ISO (lunes a domingo), con una fila TOTAL y una fila
por deporte practicado esa semana:

- **Ritmo medio ponderado por distancia**: no es la media de los ritmos de
  cada sesión, es `tiempo total / distancia total` de las sesiones de
  carrera/marcha de esa semana. Correr 10km en 50min y luego 2km en 8min da
  un ritmo semanal de 58min/12km = 4:50/km, no la media simple de 5:00 y
  4:00.
- **FC media ponderada por tiempo**: igual, ponderada por la duración de
  cada sesión, no la media simple de las medias.
- **Carga de entrenamiento (TRIMP simplificado, fórmula de Edwards, 1993)**:
  `Σ (minutos en zona de FC i) × i`, para las 5 zonas. Un minuto en zona 5
  pesa 5 veces más que uno en zona 1. Se usan las zonas de FC que Garmin ya
  calcula por actividad. No es una medida fisiológica absoluta ni comparable
  entre personas: es un índice para comparar tu propia carga de una semana a
  otra. Se expresa en "unidades arbitrarias" (UA), como es estándar en este
  tipo de índices.
- **% tiempo suave / intenso**: zonas 1-2 vs. zonas 3-5, como % del tiempo
  total con datos de FC esa semana.

### Progresión
La hoja que responde "¿he mejorado?", en tres bloques:

**Progresión semanal**: para volumen (km), tiempo, carga y ritmo — el valor
de la semana, el Δ frente a la semana ISO anterior (que puede ser una semana
de descanso con 0 sesiones: se cuenta como una semana real, no se salta) y
el Δ frente a la media móvil de las 4 semanas anteriores (sin contar la
actual), en valor y en %. Además:

- **¿Comparable?**: si esa semana tuvo menos de 2 sesiones, se marca como
  "No" y las celdas de Δ se pintan en **gris** — una sola sesión no da para
  concluir una tendencia, así que no se pinta ni verde ni rojo aunque el
  número haya subido o bajado.
- **Color**: verde = mejora, rojo = empeora. Para volumen/tiempo/carga, más
  alto se pinta verde (más entrenamiento). Para el ritmo es al revés: bajar
  el ritmo (ir más rápido por km) es la mejora, así que se pinta verde
  cuando el ritmo *baja*.
- **ACWR** (Acute:Chronic Workload Ratio): `carga media diaria de los
  últimos 7 días / carga media diaria de los últimos 28 días`. Es el ratio
  estándar de la literatura de ciencias del deporte (Gabbett, 2016); el
  rango de referencia habitual es 0.8–1.3 — subir de ahí se asocia con más
  riesgo de lesión por progresar demasiado rápido, bajar de ahí indica que
  estás perdiendo forma/detraining. Fuera de ese rango se pinta rojo. Las
  primeras ~4 semanas de uso salen como **"historial insuficiente"** (gris):
  con menos de 28 días reales de carga detrás, el promedio "crónico" está
  parcialmente vacío y el ratio saldría artificialmente alto — se prefiere
  no mostrar un aviso engañoso a mostrar uno mal calculado.

**Efficiency Factor por deporte**: `velocidad media (km/h) / FC media
(lpm)`, comparado con la última vez que se practicó ESE deporte (no con la
semana de calendario anterior, que podría ser de otro deporte). Es la
métrica que mejor detecta mejora real: ir más rápido con menos pulsaciones
es una mejora de verdad, mientras que correr más rápido pero reventado
(con la FC disparada) no lo es — el EF captura esa diferencia y el ritmo o
el volumen solos no.

**Mejores marcas**: 1km, 5km, 10km y media maratón, sacadas del campo
`fastestSplit_*` que Garmin ya calcula dentro de cada actividad (el mejor
tramo continuo de esa distancia dentro del entreno) — no se recalculan a
partir de la media de la actividad completa, que sería menos preciso.
Aparece "Sin marca todavía" para las distancias que aún no has corrido.

### Notas (rellena tú)
Cuatro columnas para escribir a mano, ligadas por `activityId`: **RPE
percibido**, **Sensaciones**, **Lesiones/molestias** y **Contexto** (dormí
mal, competición, etc.). Las columnas `activityId`/`Fecha`/`Deporte`/`Nombre`
son de referencia, se regeneran solas.

**Esto es lo más importante del fichero para el uso diario, así que la
fusión está pensada para no perderlo nunca**: cada vez que
`generate_excel.py` corre, lee primero las notas del Excel anterior (si
existe) y las vuelve a inyectar en el nuevo antes de escribir nada. El
fichero original no se toca hasta que el nuevo se ha generado por completo
en memoria y se guarda con éxito (escritura atómica vía fichero temporal).
Si el Excel anterior existe pero está corrupto y no se puede leer, el script
falla explícitamente en vez de arriesgarse a sobrescribir tus notas — mejor
un error claro que una pérdida de datos silenciosa.

### Gráficas
Todas nativas (`openpyxl.chart`), no imágenes — tocas los datos y se
actualizan solas:

1. **Volumen semanal** (barras) + **media móvil de 4 semanas** (línea).
2. **Efficiency Factor por deporte** (una línea por deporte).
3. **Carga de entrenamiento semanal + ACWR** con banda 0.8–1.3 (barras +
   línea en eje secundario).
4. **Distribución de sesiones por deporte** (pastel).
5. **Progresión de mejores marcas** (una mini-gráfica por distancia).

Se alimentan de una hoja auxiliar oculta (`_ChartData`) con las series ya
ordenadas cronológicamente — las hojas "Semanal"/"Progresión" están pensadas
para leerlas tú (más reciente arriba, filas TOTAL+deporte mezcladas), no dan
un rango de celdas limpio para graficar directamente.

## Automatización

### systemd timer (recomendado)

Unidades de usuario (no hace falta root) en `systemd/`:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/garmin-tracker.service systemd/garmin-tracker.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now garmin-tracker.timer
```

Corre los lunes a las 07:00 (con hasta 10 min de retraso aleatorio). Si el
equipo estaba apagado a esa hora, se ejecuta en cuanto vuelve a encenderse
(`Persistent=true`).

Para que el timer funcione también cuando **no has iniciado sesión**
gráficamente (por ejemplo, el ordenador está encendido pero no hay sesión
abierta), activa lingering una vez:

```bash
loginctl enable-linger "$USER"
```

**Ver logs:**

```bash
# Logs del propio servicio (systemd/journald)
journalctl --user -u garmin-tracker.service

# Seguir en vivo
journalctl --user -u garmin-tracker.service -f

# Log de la aplicación (el mismo que se ve en logs/garmin_tracker.log)
tail -f ~/garmin-tracker/logs/garmin_tracker.log
```

**Comprobar el estado / próxima ejecución:**

```bash
systemctl --user status garmin-tracker.timer
systemctl --user list-timers garmin-tracker.timer
```

**Ejecutarlo ya, sin esperar al lunes:**

```bash
systemctl --user start garmin-tracker.service
```

**Desinstalar:**

```bash
systemctl --user disable --now garmin-tracker.timer
rm ~/.config/systemd/user/garmin-tracker.{service,timer}
systemctl --user daemon-reload
```

### Alternativa: cron

Si prefieres cron en vez de systemd, la línea equivalente (`crontab -e`):

```cron
0 7 * * 1 cd $HOME/garmin-tracker && ./.venv/bin/python scripts/sync.py >> logs/cron.log 2>&1 && ./.venv/bin/python scripts/generate_excel.py >> logs/cron.log 2>&1
```

Logs en `logs/cron.log` además de `logs/garmin_tracker.log`.

## Desarrollo

`pytest` ya está en `requirements.txt`.

```bash
./.venv/bin/python -m pytest
```

Estructura del código:

- `garmin_tracker/garmin_client.py`, `retry.py` — conexión a Garmin Connect,
  reintentos con backoff.
- `garmin_tracker/storage.py`, `sync.py` — caché SQLite y sincronización
  incremental.
- `garmin_tracker/activity_model.py`, `aggregates.py`, `progression.py`,
  `training_load.py` — cálculo puro (sin tocar Garmin, SQLite ni Excel),
  testeado con datos de ejemplo fijos en `tests/fixtures.py`.
- `garmin_tracker/excel_*.py` — generación del `.xlsx` con openpyxl.

## Solución de problemas

**`401 Unauthorized` al sincronizar**: revisa `GARMIN_EMAIL`/`GARMIN_PASSWORD`
en `.env` (typos, contraseña con caracteres especiales sin comillas) y que
sea una cuenta Garmin nativa, no login social.

**`429` / rate limited**: espera unos minutos antes de reintentar; el script
ya reintenta automáticamente con backoff, pero machacar el login varias
veces seguidas hace que Garmin bloquee la IP un rato.

**El Excel no abre / parece corrupto**: no debería pasar nunca gracias a la
escritura atómica, pero si ocurre, borra `output/entrenamientos.xlsx` y
vuelve a lanzar `generate_excel.py` — los datos siguen intactos en la caché
SQLite, no hace falta volver a sincronizar con Garmin.
