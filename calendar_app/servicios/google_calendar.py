from __future__ import annotations          # Permite usar anotaciones de tipos como strings (mejora compatibilidad y typing)
from dataclasses import dataclass           # Define DTOs inmutables para transportar datos (GoogleEventCreate)
from datetime import datetime               # Manejo de fechas/horas para start y end de eventos
from typing import Any, Dict, List, Optional  # Tipos para anotaciones (claridad y validación estática)
from django.conf import settings            # Acceso a settings.py (IDs de calendarios, timezone, credenciales)
from google.oauth2.credentials import Credentials   # Maneja credenciales OAuth2 ya autorizadas (token.json)
from googleapiclient.discovery import build         # Construye el cliente de Google Calendar API
from googleapiclient.errors import HttpError        # Captura errores HTTP devueltos por Google API
from calendar_app.utils.datetime import isoformat_z # Utilidad propia para normalizar datetimes a ISO 8601 (UTC/Z)



@dataclass(frozen=True)
class GoogleEventCreate:
    """
    DTO para crear eventos de forma consistente desde la capa API.
    """
    summary: str
    start: datetime
    end: datetime
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: Optional[List[str]] = None


class GoogleCalendarService:
    """
    Servicio de acceso a Google Calendar API.

    - NO conoce HTTP ni DRF
    - Usa OAuth previamente autorizado
    - Opera sobre UN calendarId por instancia
    """

    def __init__(self, calendar_id: Optional[str] = None):
        if not calendar_id:
            calendar_id = getattr(settings, "GOOGLE_CALENDAR_ID", "primary")

        self.calendar_id = calendar_id

    # -------------------------
    # Infraestructura
    # -------------------------

    def _get_credentials(self) -> Credentials:
        token_path = getattr(settings, "GOOGLE_TOKEN_FILE", None)
        if not token_path:
            raise RuntimeError("GOOGLE_TOKEN_FILE no está configurado en settings.")

        # ✅ NO fuerces scopes aquí (usa los del token.json)
        return Credentials.from_authorized_user_file(str(token_path))


    def _client(self):
        creds = self._get_credentials()
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    # -------------------------
    # Operaciones
    # -------------------------

    def list_events(
        self,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        svc = self._client()

        params: Dict[str, Any] = {
            "calendarId": self.calendar_id,
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": max_results,
        }

        if time_min:
            params["timeMin"] = isoformat_z(time_min)
        if time_max:
            params["timeMax"] = isoformat_z(time_max)

        try:
            res = svc.events().list(**params).execute()
            return res.get("items", [])
        except HttpError as e:
            raise RuntimeError(
                f"Google Calendar list_events falló ({self.calendar_id}): {e}"
            ) from e

    def create_event(self, payload: GoogleEventCreate) -> Dict[str, Any]:
        svc = self._client()

        body: Dict[str, Any] = {
            "summary": payload.summary,
            "description": payload.description,
            "location": payload.location,
            "start": {"dateTime": isoformat_z(payload.start)},
            "end": {"dateTime": isoformat_z(payload.end)},
        }

        if payload.attendees:
            body["attendees"] = [{"email": email} for email in payload.attendees]

        body = {k: v for k, v in body.items() if v is not None}

        try:
            return svc.events().insert(
                calendarId=self.calendar_id,
                body=body
            ).execute()
        except HttpError as e:
            raise RuntimeError(
                f"Google Calendar create_event falló ({self.calendar_id}): {e}"
            ) from e

    def freebusy(self, time_min: datetime, time_max: datetime) -> Dict[str, Any]:
        svc = self._client()

        body = {
            "timeMin": isoformat_z(time_min),
            "timeMax": isoformat_z(time_max),
            "items": [{"id": self.calendar_id}],
        }

        try:
            return svc.freebusy().query(body=body).execute()
        except HttpError as e:
            raise RuntimeError(
                f"Google Calendar freebusy falló ({self.calendar_id}): {e}"
            ) from e
