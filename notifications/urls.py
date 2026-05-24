from django.urls import path

from . import views


urlpatterns = [
    path("api/notifications/subscribe/", views.subscribe, name="push_subscribe"),
    path("api/notifications/unsubscribe/", views.unsubscribe, name="push_unsubscribe"),
    path("api/notifications/status/", views.status, name="push_status"),
    path("api/notifications/mark-read/", views.mark_read, name="notifications_mark_read"),
    path("api/cron/weather-notifications/", views.weather_notifications_cron, name="weather_notifications_cron"),
    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/settings/", views.settings_page, name="notification_settings"),
]
