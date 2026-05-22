from django.urls import path

from . import views


urlpatterns = [
    path("", views.my_routes_page, name="my_routes"),
    path("<int:pk>/", views.saved_route_detail_page, name="saved_route_detail"),
    path("<int:pk>/delete/", views.saved_route_delete_page, name="saved_route_delete"),
    path("notes/", views.route_notes_page, name="route_notes"),
]
