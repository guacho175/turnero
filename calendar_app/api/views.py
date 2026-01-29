from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.shortcuts import render

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from calendar_app.api.serializers import (
    EventCreateSerializer,
    EventListQuerySerializer,
    EventOutSerializer,
    SlotCreateSerializer,
    SlotListQuerySerializer,
    SlotReserveSerializer,
)

from calendar_app.servicios.google_calendar import (
    GoogleCalendarService,
    GoogleEventCreate,
)

logger = logging.getLogger(__name__)


# -----------------------------
# Helpers (evitan redundancia)
# -----------------------------
def _calendar_map() -> Dict[str, str]:
    return getattr(settings, "GOOGLE_CALENDAR_MAP", {}) or {}


def _default_agenda() -> Optional[str]:
    # Si tienes DEFAULT_AGENDA en settings, úsalo; si no, toma la primera agenda del mapa.
    default = getattr(settings, "DEFAULT_AGENDA", None)
    if default:
        return default
    m = _calendar_map()
    return next(iter(m.keys()), None)


def _resolve_calendar_id(agenda: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Retorna (agenda_normalizada, calendar_id) o (None, None) si no se puede.
    """
    if not agenda:
        agenda = _default_agenda()

    if not agenda:
        return None, None

    m = _calendar_map()
    return agenda, m.get(agenda)


def _pick_query_params(request, allowed_keys):
    """
    Evita que serializers de query params fallen por keys extra (ej: agenda).
    """
    out = {}
    for k in allowed_keys:
        v = request.query_params.get(k)
        if v is not None and v != "":
            out[k] = v
    return out


# ------------------------------------
# Web layer (render del template HTML)
# ------------------------------------


# -----------------------------
# API: Events
# -----------------------------
class EventsView(APIView):
    """
    GET  /calendar/events?agenda=agenda1&time_min=...&time_max=...&max_results=50
    POST /calendar/events
    """

    def get(self, request):
        # Validar solo los parámetros que el serializer espera (evita que "agenda" moleste)
        query_data = _pick_query_params(request, ["time_min", "time_max", "max_results"])
        query_ser = EventListQuerySerializer(data=query_data)
        query_ser.is_valid(raise_exception=True)

        time_min = query_ser.validated_data.get("time_min")
        time_max = query_ser.validated_data.get("time_max")
        max_results = query_ser.validated_data.get("max_results", 50)

        # Agenda por querystring (selector en HTML)
        agenda_param = request.query_params.get("agenda")
        agenda, calendar_id = _resolve_calendar_id(agenda_param)

        # LOG (mantengo estilo simple)
        print("=======================================", flush=True)
        print("[API][GET] agenda(query):", agenda_param, flush=True)
        print("[API][GET] agenda(resuelta):", agenda, flush=True)
        print("[API][GET] calendar_id:", calendar_id, flush=True)
        print("[API][GET] time_min:", time_min, flush=True)
        print("[API][GET] time_max:", time_max, flush=True)
        print("[API][GET] max_results:", max_results, flush=True)
        print("=======================================", flush=True)

        if not agenda:
            return Response(
                {"detail": "No hay agenda definida. Revisa GOOGLE_CALENDAR_MAP / DEFAULT_AGENDA."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not calendar_id:
            return Response(
                {"detail": f"Agenda inválida: {agenda}", "valid": list(_calendar_map().keys())},
                status=status.HTTP_400_BAD_REQUEST,
            )

        svc = GoogleCalendarService(calendar_id=calendar_id)

        try:
            items = svc.list_events(time_min=time_min, time_max=time_max, max_results=max_results)
        except Exception as e:
            logger.exception("Error listando eventos")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        out = EventOutSerializer(items, many=True).data
        return Response(
            {"agenda": agenda, "count": len(out), "events": out},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        # 1) LOG: lo que DRF recibió realmente (antes de validar)
        print("=======================================", flush=True)
        print("[API][POST] request.data:", dict(request.data), flush=True)

        in_ser = EventCreateSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        data = in_ser.validated_data

        # 2) LOG: lo que quedó después del serializer
        print("[API][POST] validated_data:", data, flush=True)

        # 3) Agenda: preferir validated_data; fallback body
        agenda = data.get("agenda") or request.data.get("agenda")
        agenda, calendar_id = _resolve_calendar_id(agenda)

        print("[API][POST] agenda:", agenda, flush=True)
        print("[API][POST] calendar_id:", calendar_id, flush=True)
        print("=======================================", flush=True)

        if not agenda:
            return Response(
                {"detail": "Falta campo 'agenda' en el body o no hay DEFAULT_AGENDA configurada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not calendar_id:
            return Response(
                {"detail": f"Agenda inválida: {agenda}", "valid": list(_calendar_map().keys())},
                status=status.HTTP_400_BAD_REQUEST,
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

        payload = EventOutSerializer(created).data
        payload["agenda"] = agenda
        return Response(payload, status=status.HTTP_201_CREATED)


# -----------------------------
# API: FreeBusy
# -----------------------------
class FreeBusyView(APIView):
    """
    GET /calendar/freebusy?agenda=agenda1&time_min=...&time_max=...
    """

    def get(self, request):
        query_data = _pick_query_params(request, ["time_min", "time_max"])
        query_ser = EventListQuerySerializer(data=query_data)
        query_ser.is_valid(raise_exception=True)

        time_min = query_ser.validated_data.get("time_min")
        time_max = query_ser.validated_data.get("time_max")

        if not time_min or not time_max:
            return Response(
                {"detail": "Debes enviar 'time_min' y 'time_max'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        agenda_param = request.query_params.get("agenda")
        agenda, calendar_id = _resolve_calendar_id(agenda_param)

        print("=======================================", flush=True)
        print("[API][FREEBUSY] agenda(query):", agenda_param, flush=True)
        print("[API][FREEBUSY] agenda(resuelta):", agenda, flush=True)
        print("[API][FREEBUSY] calendar_id:", calendar_id, flush=True)
        print("=======================================", flush=True)

        if not agenda or not calendar_id:
            return Response(
                {"detail": f"Agenda inválida: {agenda}", "valid": list(_calendar_map().keys())},
                status=status.HTTP_400_BAD_REQUEST,
            )

        svc = GoogleCalendarService(calendar_id=calendar_id)

        try:
            res = svc.freebusy(time_min=time_min, time_max=time_max)
        except Exception as e:
            logger.exception("Error consultando freebusy")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({"agenda": agenda, "freebusy": res}, status=status.HTTP_200_OK)


# -----------------------------
# API: Slots
# -----------------------------
class SlotCreateView(APIView):
    """
    POST /calendar/agendas/<agenda>/slots

    Crea eventos tipo "slot" (DISPONIBLE) en el calendario asociado a la agenda.
    """

    def post(self, request, agenda: str):
        in_ser = SlotCreateSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        data = in_ser.validated_data

        agenda, calendar_id = _resolve_calendar_id(agenda)
        if not calendar_id:
            return Response(
                {"detail": f"Agenda inválida: {agenda}", "valid": list(_calendar_map().keys())},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # LOG
        print("=======================================", flush=True)
        print("[API][SLOT CREATE] agenda:", agenda, flush=True)
        print("[API][SLOT CREATE] calendar_id:", calendar_id, flush=True)
        print("[API][SLOT CREATE] validated_data:", data, flush=True)
        print("=======================================", flush=True)

        service_name = (data.get("service") or "").strip()
        prefix = (data.get("summary_prefix") or "DISPONIBLE").strip()
        summary = f"{prefix} - {service_name}" if service_name else prefix

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

            created.append(
                {
                    "event_id": ev.get("id"),
                    "summary": ev.get("summary"),
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                }
            )

            return Response({"agenda": agenda, "created_count": 1, "created": created}, status=status.HTTP_201_CREATED)

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

                created.append(
                    {
                        "event_id": ev.get("id"),
                        "summary": ev.get("summary"),
                        "start": ev.get("start"),
                        "end": ev.get("end"),
                    }
                )

                cursor = cursor + step_delta

        except Exception as e:
            logger.exception("Error creando slots por rango")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {"agenda": agenda, "created_count": len(created), "created": created},
            status=status.HTTP_201_CREATED,
        )


class SlotListView(APIView):
    """
    GET /calendar/agendas/<agenda>/slots?time_min=...&time_max=...&max_results=250

    Lista slots DISPONIBLES en una agenda.
    Filtro actual: description contiene 'type=slot' y 'state=available'
    """

    def get(self, request, agenda: str):
        query_ser = SlotListQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        q = query_ser.validated_data

        time_min = q.get("time_min")
        time_max = q.get("time_max")
        max_results = q.get("max_results", 250)

        agenda, calendar_id = _resolve_calendar_id(agenda)
        if not calendar_id:
            return Response(
                {"detail": f"Agenda inválida: {agenda}", "valid": list(_calendar_map().keys())},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # LOG
        print("=======================================", flush=True)
        print("[API][SLOT LIST] agenda:", agenda, flush=True)
        print("[API][SLOT LIST] calendar_id:", calendar_id, flush=True)
        print("[API][SLOT LIST] time_min:", time_min, flush=True)
        print("[API][SLOT LIST] time_max:", time_max, flush=True)
        print("[API][SLOT LIST] max_results:", max_results, flush=True)
        print("=======================================", flush=True)

        svc = GoogleCalendarService(calendar_id=calendar_id)

        try:
            items = svc.list_events(time_min=time_min, time_max=time_max, max_results=max_results)
        except Exception as e:
            logger.exception("Error listando slots")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        out = []
        for ev in items:
            desc = (ev.get("description") or "")
            summary = (ev.get("summary") or "")

            if "type=slot" not in desc:
                continue
            if "state=available" not in desc:
                continue

            out.append(
                {
                    "event_id": ev.get("id"),
                    "summary": summary,
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                }
            )

        return Response({"agenda": agenda, "count": len(out), "slots": out}, status=status.HTTP_200_OK)


class SlotReserveView(APIView):
    """
    POST /calendar/agendas/<agenda>/slots/<event_id>/reserve

    Marca un slot como reservado:
    - valida description: type=slot y state=available
    - cambia state=reserved
    - cambia summary a "RESERVADO - <cliente>"
    """

    def post(self, request, agenda: str, event_id: str):
        in_ser = SlotReserveSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        data = in_ser.validated_data

        agenda, calendar_id = _resolve_calendar_id(agenda)
        if not calendar_id:
            return Response(
                {"detail": f"Agenda inválida: {agenda}", "valid": list(_calendar_map().keys())},
                status=status.HTTP_400_BAD_REQUEST,
            )

        svc = GoogleCalendarService(calendar_id=calendar_id)

        # LOG
        print("=======================================", flush=True)
        print("[API][SLOT RESERVE] agenda:", agenda, flush=True)
        print("[API][SLOT RESERVE] calendar_id:", calendar_id, flush=True)
        print("[API][SLOT RESERVE] event_id:", event_id, flush=True)
        print("[API][SLOT RESERVE] validated_data:", data, flush=True)
        print("=======================================", flush=True)

        try:
            ev = svc.get_event(event_id)
        except Exception as e:
            logger.exception("Error obteniendo evento")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        desc = ev.get("description") or ""

        if "type=slot" not in desc:
            return Response({"detail": "El evento no es un slot (type=slot)."}, status=status.HTTP_400_BAD_REQUEST)

        if "state=available" not in desc:
            return Response(
                {"detail": "Slot no disponible (ya reservado o sin estado available)."},
                status=status.HTTP_409_CONFLICT,
            )

        new_desc = desc.replace("state=available", "state=reserved")

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

        patch_body = {
            "summary": f"RESERVADO - {customer_name}",
            "description": new_desc,
        }

        try:
            updated = svc.patch_event(event_id, patch_body)
        except Exception as e:
            logger.exception("Error reservando slot (patch)")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {
                "agenda": agenda,
                "event_id": updated.get("id"),
                "summary": updated.get("summary"),
                "start": updated.get("start"),
                "end": updated.get("end"),
                "status": "reserved",
            },
            status=status.HTTP_200_OK,
        )
