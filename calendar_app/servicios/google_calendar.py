from __future__ import annotations  # Permite usar anotaciones de tipos como strings

from dataclasses import dataclass  # Define DTOs simples e inmutables
from datetime import datetime  # Manejo de fechas y horas
from typing import Any, Dict, List, Optional  # Tipos para claridad y typing

from django.conf import settings  # Acceso a settings.py

from google.oauth2.credentials import Credentials  # Carga credenciales OAuth desde token.json
from googleapiclient.discovery import build  # Construye el cliente de Google Calendar API
from googleapiclient.errors import HttpError  # Manejo de errores HTTP de Google API

from calendar_app.utils.datetime import isoformat_z  # Convierte datetime a ISO 8601 UTC


@dataclass(frozen=True)
class GoogleEventCreate:
    """DTO para creación de eventos en Google Calendar"""
    summary: str                     # Título del evento
    start: datetime                  # Fecha/hora inicio
    end: datetime                    # Fecha/hora término
    description: Optional[str] = None  # Descripción opcional
    location: Optional[str] = None     # Ubicación opcional
    attendees: Optional[List[str]] = None  # Correos de invitados


class GoogleCalendarService:
    """Servicio que encapsula toda la interacción con Google Calendar"""

    def __init__(self, calendar_id: Optional[str] = None):
        # Usa el calendar_id entregado o el default configurado
        self.calendar_id = calendar_id or getattr(settings, "GOOGLE_CALENDAR_ID", "primary")

    # -------------------------
    # Autenticación / Cliente
    # -------------------------

    def _get_credentials(self) -> Credentials:
        # Obtiene la ruta del token OAuth generado previamente
        token_path = getattr(settings, "GOOGLE_TOKEN_FILE", None)

        if not token_path:
            raise RuntimeError("GOOGLE_TOKEN_FILE no está configurado.")

        # Carga credenciales con los scopes que quedaron grabados en token.json
        return Credentials.from_authorized_user_file(str(token_path))

    def _client(self):
        # Construye el cliente Google Calendar API v3
        creds = self._get_credentials()
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    # -------------------------
    # Operaciones Calendar
    # -------------------------

    def list_events(
        self,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        # Lista eventos del calendario
        svc = self._client()

        params: Dict[str, Any] = {
            "calendarId": self.calendar_id,
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": max_results,
        }

        # Filtro por fecha mínima
        if time_min:
            params["timeMin"] = isoformat_z(time_min)

        # Filtro por fecha máxima
        if time_max:
            params["timeMax"] = isoformat_z(time_max)

        try:
            # Ejecuta llamada events.list
            res = svc.events().list(**params).execute()
            return res.get("items", [])
        except HttpError as e:
            raise RuntimeError(
                f"Google Calendar list_events falló ({self.calendar_id}): {e}"
            ) from e

    def create_event(self, payload: GoogleEventCreate) -> Dict[str, Any]:
        # Crea un evento en Google Calendar
        svc = self._client()

        body: Dict[str, Any] = {
            "summary": payload.summary,
            "description": payload.description,
            "location": payload.location,
            "start": {"dateTime": isoformat_z(payload.start)},
            "end": {"dateTime": isoformat_z(payload.end)},
        }

        # Agrega invitados si existen
        if payload.attendees:
            body["attendees"] = [{"email": email} for email in payload.attendees]

        # Elimina campos None
        body = {k: v for k, v in body.items() if v is not None}

        try:
            # Inserta evento y envía correos a invitados
            return svc.events().insert(
                calendarId=self.calendar_id,
                body=body,
                sendUpdates="all",
            ).execute()
        except HttpError as e:
            raise RuntimeError(
                f"Google Calendar create_event falló ({self.calendar_id}): {e}"
            ) from e

    def freebusy(self, time_min: datetime, time_max: datetime) -> Dict[str, Any]:
        # Consulta bloques ocupados (free/busy)
        svc = self._client()

        body = {
            "timeMin": isoformat_z(time_min),
            "timeMax": isoformat_z(time_max),
            "items": [{"id": self.calendar_id}],
        }

        try:
            # Ejecuta freeBusy.query (requiere scopes adecuados)
            return svc.freebusy().query(body=body).execute()
        except HttpError as e:
            raise RuntimeError(
                f"Google Calendar freebusy falló ({self.calendar_id}): {e}"
            ) from e

    def get_event(self, event_id: str) -> Dict[str, Any]:
        # Obtiene un evento por ID
        svc = self._client()

        try:
            return svc.events().get(
                calendarId=self.calendar_id,
                eventId=event_id,
            ).execute()
        except HttpError as e:
            raise RuntimeError(
                f"Google Calendar get_event falló ({self.calendar_id}, {event_id}): {e}"
            ) from e

    def patch_event(self, event_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        # Actualiza parcialmente un evento existente
        svc = self._client()

        try:
            return svc.events().patch(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=body,
                sendUpdates="all",
            ).execute()
        except HttpError as e:
            raise RuntimeError(
                f"Google Calendar patch_event falló ({self.calendar_id}, {event_id}): {e}"
            ) from e
