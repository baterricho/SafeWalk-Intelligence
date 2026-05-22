from django.urls import path

from .views import reverse_geocode_view


urlpatterns = [
    path("reverse/", reverse_geocode_view, name="reverse_geocode"),
]
