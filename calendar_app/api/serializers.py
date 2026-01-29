from __future__ import annotations          # Permite usar anotaciones de tipos como strings (typing moderno)

from datetime import datetime               # Manejo de fechas/horas para validaciones (start/end)

from rest_framework import serializers      # Serializers de Django REST Framework (validación y parsing)



class EventListQuerySerializer(serializers.Serializer):
    """
    Valida query params para filtrar el listado.
    """
    time_min = serializers.DateTimeField(required=False)
    time_max = serializers.DateTimeField(required=False)
    max_results = serializers.IntegerField(required=False, min_value=1, max_value=250, default=50)


class EventCreateSerializer(serializers.Serializer):
    """
    Valida el payload de creación de eventos.
    """
    agenda = serializers.CharField(required=False, allow_blank=False, default="agenda1")

    summary = serializers.CharField(max_length=200)
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    attendees = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        allow_empty=True
    )

    def validate(self, attrs):
        start: datetime = attrs["start"]
        end: datetime = attrs["end"]
        if end <= start:
            raise serializers.ValidationError("La fecha/hora 'end' debe ser mayor que 'start'.")
        return attrs


class EventOutSerializer(serializers.Serializer):
    """
    Normaliza salida (no exponemos el objeto crudo completo si no hace falta).
    """
    id = serializers.CharField()
    summary = serializers.CharField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_null=True)
    location = serializers.CharField(required=False, allow_null=True)

    start = serializers.DictField()
    end = serializers.DictField()

    htmlLink = serializers.CharField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_null=True)
    agenda = serializers.CharField(required=False, allow_blank=False)


class SlotCreateSerializer(serializers.Serializer):
    # Opción A: crear 1 slot exacto
    start = serializers.DateTimeField(required=False)
    end = serializers.DateTimeField(required=False)

    # Opción B: crear muchos slots por rango
    range_start = serializers.DateTimeField(required=False)
    range_end = serializers.DateTimeField(required=False)
    slot_minutes = serializers.IntegerField(required=False, min_value=5)
    step_minutes = serializers.IntegerField(required=False, min_value=5)

    service = serializers.CharField(required=False, allow_blank=True, max_length=120)
    summary_prefix = serializers.CharField(required=False, allow_blank=True, max_length=60, default="DISPONIBLE")

    def validate(self, data):
        single = ("start" in data) or ("end" in data)
        batch = ("range_start" in data) or ("range_end" in data)

        if single and batch:
            raise serializers.ValidationError("Usa start/end o range_start/range_end, no ambos.")

        if single:
            if "start" not in data or "end" not in data:
                raise serializers.ValidationError("Para slot único debes enviar start y end.")
            if data["end"] <= data["start"]:
                raise serializers.ValidationError("end debe ser mayor que start.")
            return data

        if batch:
            required = ["range_start", "range_end", "slot_minutes", "step_minutes"]
            for k in required:
                if k not in data:
                    raise serializers.ValidationError(f"Falta {k} para creación por rango.")
            if data["range_end"] <= data["range_start"]:
                raise serializers.ValidationError("range_end debe ser mayor que range_start.")
            return data

        raise serializers.ValidationError("Debes enviar start/end o range_start/range_end.")


class SlotListQuerySerializer(serializers.Serializer):
    time_min = serializers.DateTimeField(required=False)
    time_max = serializers.DateTimeField(required=False)
    max_results = serializers.IntegerField(required=False, min_value=1, max_value=250, default=250)

    def validate(self, data):
        # Reglas mínimas: si viene uno, debe venir el otro
        if ("time_min" in data) ^ ("time_max" in data):
            raise serializers.ValidationError("Debes enviar ambos: time_min y time_max, o ninguno.")
        if "time_min" in data and data["time_max"] <= data["time_min"]:
            raise serializers.ValidationError("time_max debe ser mayor que time_min.")
        return data


class SlotReserveSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=120)
    customer_phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)