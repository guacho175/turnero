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

