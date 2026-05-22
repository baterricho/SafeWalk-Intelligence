from django.urls import path

from .views import (
    AdminDashboardAPIView,
    AdminReportDeleteAPIView,
    AdminReportHistoryAPIView,
    AdminReportStatusAPIView,
    AdminReportsAPIView,
)


urlpatterns = [
    path("dashboard/", AdminDashboardAPIView.as_view(), name="admin_dashboard_api"),
    path("reports/", AdminReportsAPIView.as_view(), name="admin_reports_api"),
    path("reports/<int:pk>/status/", AdminReportStatusAPIView.as_view(), name="admin_report_status_api"),
    path("reports/<int:pk>/history/", AdminReportHistoryAPIView.as_view(), name="admin_report_history_api"),
    path("reports/<int:pk>/", AdminReportDeleteAPIView.as_view(), name="admin_report_delete_api"),
]
