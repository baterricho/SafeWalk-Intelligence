from django.http import JsonResponse
from django.db import connection
from django.conf import settings


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
