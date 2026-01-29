from django.urls import path

from calendar_app.api.views import EventsView, FreeBusyView, SlotCreateView, SlotListView,SlotReserveView
from calendar_app.web.views import calendar_page

urlpatterns = [
    
     # WEB (agenda visual)

    path("", calendar_page, name="calendar_page"),

    # API
    path("events", EventsView.as_view(), name="calendar-events"),
    path("freebusy", FreeBusyView.as_view(), name="calendar-freebusy"),


    path("agendas/<str:agenda>/slots",SlotCreateView.as_view(),name="calendar-slots-create"),
    path("agendas/<str:agenda>/slots/list", SlotListView.as_view(), name="calendar-slots-list"),
    path("agendas/<str:agenda>/slots/<str:event_id>/reserve",SlotReserveView.as_view(),name="calendar-slot-reserve"),


]
