from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AreaClustersAPIView,
    AreaSummaryAPIView,
    AreaTimelineAPIView,
    ConfirmationDetailAPIView,
    SafetyReportViewSet,
)


router = DefaultRouter()
router.register("reports", SafetyReportViewSet, basename="reports")

urlpatterns = [
    path("", include(router.urls)),
    path("confirmations/<int:pk>/", ConfirmationDetailAPIView.as_view(), name="confirmation_detail"),
    path("areas/clusters/", AreaClustersAPIView.as_view(), name="area_clusters"),
    path("areas/<str:location_name>/summary/", AreaSummaryAPIView.as_view(), name="area_summary_api"),
    path("areas/<str:location_name>/timeline/", AreaTimelineAPIView.as_view(), name="area_timeline_api"),
]
