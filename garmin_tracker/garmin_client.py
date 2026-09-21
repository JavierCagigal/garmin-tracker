"""Conexión y autenticación contra Garmin Connect.

Usa la librería `garminconnect` (cyberjunky/python-garminconnect). El login
cachea tokens OAuth en `tokenstore` (ver Settings.tokenstore); en ejecuciones
posteriores no vuelve a pedir usuario/contraseña ni MFA salvo que el refresh
token caduque o se revoque.
"""

from __future__ import annotations

import logging

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
)

from garmin_tracker.config import Settings
from garmin_tracker.retry import call_with_retry

logger = logging.getLogger(__name__)


def _prompt_mfa() -> str:
    return input("Código MFA de Garmin Connect: ").strip()


def get_client(settings: Settings) -> Garmin:
    """Devuelve un cliente Garmin ya autenticado.

    Requiere una terminal interactiva la primera vez si la cuenta tiene MFA
    activado (para introducir el código). En ejecuciones posteriores reutiliza
    los tokens cacheados en `settings.tokenstore` y no debería pedir nada.
    """
    client = Garmin(
        email=settings.garmin_email,
        password=settings.garmin_password,
        prompt_mfa=_prompt_mfa,
    )
    try:
        call_with_retry(
            lambda: client.login(settings.tokenstore),
            description="login en Garmin Connect",
        )
    except GarminConnectAuthenticationError:
        logger.error(
            "Autenticación rechazada por Garmin. Revisa GARMIN_EMAIL/GARMIN_PASSWORD "
            "en .env, o borra %s si los tokens cacheados están corruptos.",
            settings.tokenstore,
        )
        raise
    except GarminConnectConnectionError:
        logger.error("No se pudo conectar con Garmin Connect (red o servicio caído).")
        raise
    logger.info("Login en Garmin Connect correcto (tokens en %s).", settings.tokenstore)
    return client
