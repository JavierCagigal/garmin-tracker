"""Carga de entrenamiento: TRIMP simplificado por zonas de FC (Edwards, 1993).

    TRIMP = Σ (minutos en zona i) × i,  para i = 1..5

Es una versión simplificada del TRIMP clásico de Banister, que necesita FC
máxima y FC de reposo del usuario (datos que no tenemos configurados en
ningún sitio). La versión de Edwards usa directamente el tiempo por zona de
FC que Garmin ya calcula por actividad (`hrTimeInZone_1`..`hrTimeInZone_5`),
ponderando cada zona por su número: un minuto en zona 5 (muy intensa) pesa 5
veces más que un minuto en zona 1 (muy suave).

No es una medida fisiológica absoluta ni comparable entre personas — es un
índice relativo pensado para comparar TU propia carga de una semana a otra.
El resultado se expresa en unidades arbitrarias (UA), como es estándar en
este tipo de índices.
"""

from __future__ import annotations

ZONE_WEIGHTS: tuple[int, int, int, int, int] = (1, 2, 3, 4, 5)


def edwards_trimp(hr_zone_seconds: tuple[float | None, ...]) -> float | None:
    """Carga de una actividad a partir de sus 5 zonas de FC (en segundos).

    Devuelve None si no hay ningún dato de zona (actividad sin FC, p.ej.
    algunas de fuerza sin banda). Si hay datos parciales, las zonas ausentes
    cuentan como 0 segundos (no como "desconocido"), porque si Garmin
    reportó al menos una zona es que sí midió FC durante la actividad.
    """
    if len(hr_zone_seconds) != 5:
        raise ValueError("Se esperan exactamente 5 zonas de FC (1 a 5)")
    if all(z is None for z in hr_zone_seconds):
        return None
    return sum((seconds or 0.0) / 60.0 * weight for seconds, weight in zip(hr_zone_seconds, ZONE_WEIGHTS))
