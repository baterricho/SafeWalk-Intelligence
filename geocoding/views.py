from django.http import JsonResponse

from .services import reverse_geocode


def reverse_geocode_view(request):
    latitude = request.GET.get("lat")
    longitude = request.GET.get("lng")
    result = reverse_geocode(latitude, longitude)
    status = 400 if result.get("invalid_request") or latitude is None or longitude is None else 200
    return JsonResponse(result, status=status)
