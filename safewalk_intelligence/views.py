from django.http import JsonResponse
from django.db import connection


def health_check(request):
    data = {
        "status": "ok",
        "database": "connected",
        "static": "ok",
    }
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        data["status"] = "error"
        data["database"] = f"error: {str(e)}"
    
    return JsonResponse(data)
