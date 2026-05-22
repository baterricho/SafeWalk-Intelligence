from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RouteNoteViewSet, SavedRouteViewSet


router = DefaultRouter()
router.register("route-notes", RouteNoteViewSet, basename="route-notes")
router.register("saved-routes", SavedRouteViewSet, basename="saved-routes")

urlpatterns = [
    path("", include(router.urls)),
]
