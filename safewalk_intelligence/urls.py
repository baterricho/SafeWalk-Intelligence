from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts import views as account_views
from dashboard import views as dashboard_views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("reports.urls")),
    path("api/", include("routes.urls")),
    path("api/admin/", include("dashboard.urls")),
    path("api/geocoding/", include("geocoding.urls")),
    path("api/weather/", dashboard_views.weather_api, name="weather_api"),
    path("accounts/", include("allauth.urls")),
    path("", dashboard_views.home_page, name="home"),
    path("dashboard/", dashboard_views.user_dashboard_page, name="dashboard"),
    path("admin-dashboard/", dashboard_views.admin_dashboard_page, name="admin_dashboard"),
    path("admin-dashboard/reports/", dashboard_views.admin_reports_page, name="admin_reports_page"),
    path("login/", account_views.login_page, name="login"),
    path("logout/", account_views.logout_page, name="logout"),
    path("signup/", account_views.register_page, name="signup"),
    path("register/", account_views.register_page, name="register"),
    path("reports/", include("reports.web_urls")),
    path("routes/", include("routes.web_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
