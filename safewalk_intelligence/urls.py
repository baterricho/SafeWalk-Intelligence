from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

from accounts import views as account_views
from dashboard import views as dashboard_views


from .views import download_android_apk, health_check, service_worker, web_manifest

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("download/android/", download_android_apk, name="download_android_apk"),
    path("offline/", TemplateView.as_view(template_name="offline.html"), name="offline"),
    path("manifest.json", web_manifest, name="web_manifest"),
    path("service-worker.js", service_worker, name="service_worker"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("reports.urls")),
    path("api/", include("routes.urls")),
    path("api/admin/", include("dashboard.urls")),
    path("api/geocoding/", include("geocoding.urls")),
    path("", include("notifications.urls")),
    path("api/dashboard/reports/", dashboard_views.dashboard_reports_api, name="dashboard_reports_api"),
    path("api/weather/", dashboard_views.weather_api, name="weather_api"),
    path("accounts/", include("allauth.urls")),
    path("", dashboard_views.home_page, name="home"),
    path("dashboard/", dashboard_views.user_dashboard_page, name="dashboard"),
    path("dashboard/admin/", RedirectView.as_view(pattern_name="admin_dashboard", permanent=False)),
    path("admin-dashboard/", dashboard_views.admin_dashboard_page, name="admin_dashboard"),
    path("admin-dashboard/reports/", dashboard_views.admin_reports_page, name="admin_reports_page"),
    path("login/", account_views.login_page, name="login"),
    path("logout/", account_views.logout_page, name="logout"),
    path("signup/", account_views.register_page, name="signup"),
    path("register/", account_views.register_page, name="register"),
    path("reports/", include("reports.web_urls")),
    path("routes/", include("routes.web_urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
