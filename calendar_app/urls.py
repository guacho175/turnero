from django.urls import path

from calendar_app.api.views import EventsView, FreeBusyView
from calendar_app.web.views import calendar_page

urlpatterns = [
    
     # WEB (agenda visual)

    path("", calendar_page, name="calendar_page"),

    # API
    path("events", EventsView.as_view(), name="calendar-events"),
    path("freebusy", FreeBusyView.as_view(), name="calendar-freebusy"),


]
