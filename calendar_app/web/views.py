from django.shortcuts import render


def calendar_page(request):
    """
    Renderiza una vista simple que consume /calendar/events por fetch
    y muestra un calendario visual.
    """
    return render(request, "calendar_app/calendar.html")
