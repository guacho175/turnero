from __future__ import annotations          # Permite usar anotaciones de tipos como strings (typing moderno)
import logging                              # Sistema de logging estándar de Python (logs estructurados)
from django.conf import settings            # Acceso a settings.py (mapa de agendas, calendar IDs, timezone)
from rest_framework import status           # Códigos HTTP (200, 201, 400, 502, etc.)
from rest_framework.response import Response # Respuesta HTTP JSON de Django REST Framework
from rest_framework.views import APIView    # Base class para crear endpoints REST (GET/POST)

from calendar_app.api.serializers import (  # Serializers DRF: validan input y normalizan output
    EventCreateSerializer,                  # Valida payload de creación de eventos (incluye agenda)
    EventListQuerySerializer,               # Valida query params del listado de eventos
    EventOutSerializer,                     # Normaliza la respuesta del evento creado/listado
)

from calendar_app.servicios.google_calendar import (  # Servicio de integración con Google Calendar API
    GoogleCalendarService,                  # Cliente que opera sobre un calendarId específico
    GoogleEventCreate,                      # DTO del evento (summary, start, end, etc.)
)


logger = logging.getLogger(__name__)


class EventsView(APIView):
    """
    GET  /calendar/events?time_min=...&time_max=...&max_results=50
    POST /calendar/events
    """

    def get(self, request):
        query_ser = EventListQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)

        time_min = query_ser.validated_data.get("time_min")
        time_max = query_ser.validated_data.get("time_max")
        max_results = query_ser.validated_data.get("max_results", 50)

        svc = GoogleCalendarService()

        try:
            items = svc.list_events(time_min=time_min, time_max=time_max, max_results=max_results)
        except Exception as e:
            logger.exception("Error listando eventos")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        out = EventOutSerializer(items, many=True).data
        return Response({"count": len(out), "events": out}, status=status.HTTP_200_OK)

    def post(self, request):
        # 1) LOG: lo que DRF recibió realmente (antes de validar)
        print("=======================================", flush=True)
        print("[API] request.data:", dict(request.data), flush=True)

        in_ser = EventCreateSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        data = in_ser.validated_data

        # 2) LOG: lo que quedó después del serializer
        print("[API] validated_data:", data, flush=True)

        # 3) Agenda: primero desde validated_data (lo correcto)
        agenda = data.get("agenda")

        # 4) Diagnóstico: si el serializer no la incluye, intenta leer directo del body
        if agenda is None:
            agenda = request.data.get("agenda")

        calendar_map = getattr(settings, "GOOGLE_CALENDAR_MAP", {})
        calendar_id = calendar_map.get(agenda)

        print("[API] agenda:", agenda, flush=True)
        print("[API] calendar_id:", calendar_id, flush=True)
        print("=======================================", flush=True)

        if not agenda:
            return Response(
                {"detail": "Falta campo 'agenda' en el body o el serializer lo está descartando."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not calendar_id:
            return Response(
                {"detail": f"Agenda inválida: {agenda}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        dto = GoogleEventCreate(
            summary=data["summary"],
            start=data["start"],
            end=data["end"],
            description=data.get("description"),
            location=data.get("location"),
            attendees=data.get("attendees"),
        )

        try:
            svc = GoogleCalendarService(calendar_id=calendar_id)
            created = svc.create_event(dto)
        except Exception as e:
            logger.exception("Error creando evento")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(EventOutSerializer(created).data, status=status.HTTP_201_CREATED)


class FreeBusyView(APIView):
    """
    GET /calendar/freebusy?time_min=...&time_max=...
    """

    def get(self, request):
        query_ser = EventListQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)

        time_min = query_ser.validated_data.get("time_min")
        time_max = query_ser.validated_data.get("time_max")

        if not time_min or not time_max:
            return Response(
                {"detail": "Debes enviar 'time_min' y 'time_max'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        svc = GoogleCalendarService()

        try:
            res = svc.freebusy(time_min=time_min, time_max=time_max)
        except Exception as e:
            logger.exception("Error consultando freebusy")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(res, status=status.HTTP_200_OK)
