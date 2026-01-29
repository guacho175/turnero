from django.shortcuts import render
from calendar_app.api.views import _calendar_map, _default_agenda





def calendar_page(request):
    """
    Renderiza el HTML del calendario y entrega al template
    el listado de agendas (para selector dinámico).

    El template puede usar:
      - agendas: [{"key": "agenda1", "calendar_id": "..."}...]
      - default_agenda: "agenda1"
    """
    m = _calendar_map()
    default_agenda = _default_agenda()

    agendas = [{"key": k, "calendar_id": v} for k, v in m.items()]

    return render(
        request,
        "calendar_app/calendar.html",
        {
            "agendas": agendas,
            "default_agenda": default_agenda,
        },
    )
