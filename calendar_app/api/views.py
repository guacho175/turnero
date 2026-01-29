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
from datetime import timedelta
from calendar_app.api.serializers import SlotCreateSerializer,SlotListQuerySerializer,SlotReserveSerializer

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

# SlotCreateView
# Generación masiva de slots de disponibilidad (no reservas)
class SlotCreateView(APIView):
    """
    POST /calendar/agendas/<agenda>/slots

    Crea eventos tipo "slot" (DISPONIBLE) en el calendario asociado a la agenda.
    Reusa settings.GOOGLE_CALENDAR_MAP igual que EventsView.post().
    """

    def post(self, request, agenda: str):
        in_ser = SlotCreateSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        data = in_ser.validated_data

        # 1) Resolver calendar_id desde el mapa existente
        calendar_map = getattr(settings, "GOOGLE_CALENDAR_MAP", {})
        calendar_id = calendar_map.get(agenda)

        if not calendar_id:
            return Response(
                {"detail": f"Agenda inválida: {agenda}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2) Armar summary base del slot
        service_name = (data.get("service") or "").strip()
        prefix = (data.get("summary_prefix") or "DISPONIBLE").strip()
        summary = f"{prefix} - {service_name}" if service_name else prefix

        # 3) Cliente Google Calendar apuntando a la agenda correcta
        svc = GoogleCalendarService(calendar_id=calendar_id)

        created = []

        # Caso A: slot único (start/end)
        if "start" in data:
            dto = GoogleEventCreate(
                summary=summary,
                start=data["start"],
                end=data["end"],
                description="type=slot\nstate=available",
                attendees=[],
            )
            try:
                ev = svc.create_event(dto)
            except Exception as e:
                logger.exception("Error creando slot único")
                return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

            created.append({
                "event_id": ev.get("id"),
                "summary": ev.get("summary"),
                "start": ev.get("start"),
                "end": ev.get("end"),
            })

            return Response({"created_count": 1, "created": created}, status=status.HTTP_201_CREATED)

        # Caso B: slots por rango (range_start/range_end)
        range_start = data["range_start"]
        range_end = data["range_end"]
        slot_minutes = data["slot_minutes"]
        step_minutes = data["step_minutes"]

        cursor = range_start
        slot_delta = timedelta(minutes=slot_minutes)
        step_delta = timedelta(minutes=step_minutes)

        try:
            while cursor + slot_delta <= range_end:
                slot_end = cursor + slot_delta

                dto = GoogleEventCreate(
                    summary=summary,
                    start=cursor,
                    end=slot_end,
                    description="type=slot\nstate=available",
                    attendees=[],
                )
                ev = svc.create_event(dto)
                created.append({
                    "event_id": ev.get("id"),
                    "summary": ev.get("summary"),
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                })

                cursor = cursor + step_delta

        except Exception as e:
            logger.exception("Error creando slots por rango")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {"created_count": len(created), "created": created},
            status=status.HTTP_201_CREATED
        )



class SlotListView(APIView):
    """
    GET /calendar/agendas/<agenda>/slots?time_min=...&time_max=...&max_results=250

    Lista bloques DISPONIBLES (slots) en una agenda.
    Filtro actual (MVP): description contiene 'type=slot' y 'state=available'
    """

    def get(self, request, agenda: str):
        query_ser = SlotListQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        q = query_ser.validated_data

        time_min = q.get("time_min")
        time_max = q.get("time_max")
        max_results = q.get("max_results", 250)

        calendar_map = getattr(settings, "GOOGLE_CALENDAR_MAP", {})
        calendar_id = calendar_map.get(agenda)

        if not calendar_id:
            return Response({"detail": f"Agenda inválida: {agenda}"}, status=status.HTTP_400_BAD_REQUEST)

        svc = GoogleCalendarService(calendar_id=calendar_id)

        try:
            items = svc.list_events(time_min=time_min, time_max=time_max, max_results=max_results)
        except Exception as e:
            logger.exception("Error listando slots")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        # --- Filtro: SOLO slots disponibles ---
        out = []
        for ev in items:
            desc = (ev.get("description") or "")
            summary = (ev.get("summary") or "")

            is_slot = ("type=slot" in desc)
            is_available = ("state=available" in desc)

            # fallback por si algún slot quedó sin description (opcional)
            if not is_slot:
                continue
            if not is_available:
                continue

            out.append({
                "event_id": ev.get("id"),
                "summary": summary,
                "start": ev.get("start"),
                "end": ev.get("end"),
            })

        return Response({"count": len(out), "slots": out}, status=status.HTTP_200_OK)



class SlotReserveView(APIView):
    """
    POST /calendar/agendas/<agenda>/slots/<event_id>/reserve

    Marca un slot como reservado:
    - valida que description contenga type=slot y state=available
    - cambia state=reserved
    - cambia summary a "RESERVADO - <cliente>"
    """

    def post(self, request, agenda: str, event_id: str):
        in_ser = SlotReserveSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        data = in_ser.validated_data

        # 1) resolver calendar_id (reutiliza tu patrón actual)
        calendar_map = getattr(settings, "GOOGLE_CALENDAR_MAP", {})
        calendar_id = calendar_map.get(agenda)
        if not calendar_id:
            return Response({"detail": f"Agenda inválida: {agenda}"}, status=status.HTTP_400_BAD_REQUEST)

        svc = GoogleCalendarService(calendar_id=calendar_id)

        # 2) leer evento actual
        try:
            ev = svc.get_event(event_id)
        except Exception as e:
            logger.exception("Error obteniendo evento")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        desc = ev.get("description") or ""
        summary = ev.get("summary") or ""

        # 3) validar que sea slot disponible
        if "type=slot" not in desc:
            return Response({"detail": "El evento no es un slot (type=slot)."}, status=status.HTTP_400_BAD_REQUEST)

        if "state=available" not in desc:
            return Response({"detail": "Slot no disponible (ya reservado o sin estado available)."}, status=status.HTTP_409_CONFLICT)

        # 4) construir nuevo description cambiando el estado
        new_desc = desc.replace("state=available", "state=reserved")

        # info extra (opcional) para trazabilidad
        customer_name = data["customer_name"].strip()
        customer_phone = (data.get("customer_phone") or "").strip()
        notes = (data.get("notes") or "").strip()

        extra_lines = []
        if customer_phone:
            extra_lines.append(f"customer_phone={customer_phone}")
        if notes:
            extra_lines.append(f"notes={notes}")

        if extra_lines:
            new_desc = new_desc + "\n" + "\n".join(extra_lines)

        # 5) patch del evento
        patch_body = {
            "summary": f"RESERVADO - {customer_name}",
            "description": new_desc,
        }

        try:
            updated = svc.patch_event(event_id, patch_body)
        except Exception as e:
            logger.exception("Error reservando slot (patch)")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            "event_id": updated.get("id"),
            "summary": updated.get("summary"),
            "start": updated.get("start"),
            "end": updated.get("end"),
            "status": "reserved"
        }, status=status.HTTP_200_OK)
