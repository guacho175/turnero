from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


def get_tz() -> ZoneInfo:
    """
    Retorna el timezone oficial del proyecto para Calendar.
    Centralizar esto evita inconsistencias en parseos/formatos.
    """
    return ZoneInfo(getattr(settings, "CALENDAR_TIMEZONE", "UTC"))


def to_aware(dt: datetime) -> datetime:
    """
    Convierte un datetime naive a aware usando el timezone del proyecto.
    Si ya es aware, lo retorna tal cual.
    """
    if timezone.is_aware(dt):
        return dt
    return dt.replace(tzinfo=get_tz())


def isoformat_z(dt: datetime) -> str:
    """
    Convierte a ISO 8601 (RFC3339-friendly) para Google Calendar.
    """
    return to_aware(dt).isoformat()
