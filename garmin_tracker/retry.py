"""Reintentos con backoff exponencial para llamadas a la API de Garmin."""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

from garminconnect import GarminConnectConnectionError, GarminConnectTooManyRequestsError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Errores transitorios de red/rate-limit: tiene sentido reintentar. Cualquier
# otra excepción (p.ej. GarminConnectAuthenticationError) se propaga de
# inmediato porque reintentar no la va a arreglar.
RETRYABLE_EXCEPTIONS = (GarminConnectConnectionError, GarminConnectTooManyRequestsError)


def call_with_retry(
    func: Callable[[], T],
    *,
    max_attempts: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    description: str = "llamada a Garmin",
) -> T:
    """Ejecuta `func` reintentando con backoff exponencial + jitter.

    :param max_attempts: número total de intentos (incluido el primero).
    :param base_delay: espera antes del 2º intento, en segundos; se duplica
        en cada intento posterior hasta `max_delay`.
    """
    attempt = 1
    while True:
        try:
            return func()
        except RETRYABLE_EXCEPTIONS as exc:
            if attempt >= max_attempts:
                logger.error(
                    "%s: agotados %d intentos, abandono. Último error: %s",
                    description, max_attempts, exc,
                )
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay *= 1 + random.random() * 0.25  # jitter para no sincronizar reintentos
            logger.warning(
                "%s falló (intento %d/%d): %s. Reintentando en %.1fs...",
                description, attempt, max_attempts, exc, delay,
            )
            time.sleep(delay)
            attempt += 1
