from django.urls import path

from . import views


urlpatterns = [
    path("", views.my_routes_page, name="my_routes"),
    path("notes/", views.route_notes_page, name="route_notes"),
]
