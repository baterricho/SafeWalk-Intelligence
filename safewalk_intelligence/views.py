from django.conf import settings
from django.contrib.staticfiles import finders
from django.db import connection
from django.http import FileResponse, Http404, JsonResponse


def health_check(request):
    data = {
        "status": "ok",
        "database": "connected",
        "static": "ok",
        "google_oauth": "not_configured",
    }
    
    # Check Google OAuth Config
    google_config = settings.SOCIALACCOUNT_PROVIDERS.get("google", {}).get("APP", {})
    client_id = google_config.get("client_id", "")
    secret = google_config.get("secret", "")
    
    if client_id and secret:
        data["google_oauth"] = f"configured (ID ends in {client_id[-12:]})"
    elif client_id:
        data["google_oauth"] = "missing_secret"
    elif secret:
        data["google_oauth"] = "missing_client_id"

    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        data["status"] = "error"
        data["database"] = f"error: {str(e)}"
    
    return JsonResponse(data)


def service_worker(request):
    service_worker_path = finders.find("js/service-worker.js")
    if not service_worker_path:
        raise Http404("Service worker not found.")

    response = FileResponse(open(service_worker_path, "rb"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def web_manifest(request):
    manifest_path = finders.find("manifest.json")
    if not manifest_path:
        raise Http404("Manifest not found.")

    response = FileResponse(open(manifest_path, "rb"), content_type="application/manifest+json")
    response["Cache-Control"] = "no-cache"
    return response
