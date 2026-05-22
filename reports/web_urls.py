from django.urls import path

from . import views


urlpatterns = [
    path("", views.report_list_page, name="report_list"),
    path("new/", views.report_create_page, name="report_create"),
    path("<int:pk>/", views.report_detail_page, name="report_detail"),
    path("<int:pk>/edit/", views.report_update_page, name="report_edit"),
    path("<int:pk>/delete/", views.report_delete_page, name="report_delete"),
    path("areas/<str:location_name>/", views.area_summary_page, name="area_summary_page"),
]
