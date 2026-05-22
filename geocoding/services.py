from decimal import Decimal, InvalidOperation
import time

from django.core.cache import cache
import requests


NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_USER_AGENT = "SafeWalkIntelligence/1.0 (local Django student project; contact: admin@safewalk.com)"
GEOCODE_CACHE_SECONDS = 60 * 60 * 24
NOMINATIM_MIN_INTERVAL_SECONDS = 1.0


def validate_coordinate(value, minimum, maximum, label):
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} must be a valid number.")
    if decimal_value < Decimal(str(minimum)) or decimal_value > Decimal(str(maximum)):
        raise ValueError(f"{label} is outside the valid range.")
    return decimal_value


def compact_join(parts):
    cleaned = []
    for part in parts:
        if part and part not in cleaned:
            cleaned.append(part)
    return ", ".join(cleaned)


def format_location_name(nominatim_data):
    address = nominatim_data.get("address") or {}
    display_name = nominatim_data.get("display_name", "")

    road = address.get("road") or address.get("pedestrian") or address.get("footway")
    named_place = address.get("amenity") or address.get("building") or nominatim_data.get("name")
    neighbourhood = (
        address.get("neighbourhood")
        or address.get("suburb")
        or address.get("village")
        or address.get("barangay")
        or address.get("quarter")
        or address.get("city_district")
    )
    city = address.get("city") or address.get("town") or address.get("municipality")
    province = address.get("state") or address.get("province")
    country = address.get("country")

    if named_place and city:
        short_name = compact_join([named_place, city])
    elif named_place and neighbourhood:
        short_name = compact_join([named_place, neighbourhood])
    elif road and city:
        short_name = compact_join([road, city])
    elif road and neighbourhood:
        short_name = compact_join([road, neighbourhood])
    elif neighbourhood and city:
        short_name = compact_join([neighbourhood, city])
    elif city and province:
        short_name = compact_join([city, province])
    elif neighbourhood and province:
        short_name = compact_join([neighbourhood, province])
    else:
        short_name = compact_join([city, province, country]) or display_name

    display = display_name or compact_join([neighbourhood, city, province, country])
    return {
        "display_name": display,
        "short_name": short_name or display or "Pinned location",
    }


def throttle_nominatim_request():
    last_request = cache.get("nominatim_last_request_at")
    now = time.monotonic()
    if last_request:
        elapsed = now - float(last_request)
        if elapsed < NOMINATIM_MIN_INTERVAL_SECONDS:
            time.sleep(NOMINATIM_MIN_INTERVAL_SECONDS - elapsed)
    cache.set("nominatim_last_request_at", time.monotonic(), timeout=60)


def reverse_geocode(latitude, longitude):
    try:
        lat = validate_coordinate(latitude, -90, 90, "Latitude")
        lng = validate_coordinate(longitude, -180, 180, "Longitude")
    except ValueError as exc:
        return {"success": False, "message": str(exc), "invalid_request": True}

    rounded_lat = round(float(lat), 6)
    rounded_lng = round(float(lng), 6)
    cache_key = f"reverse_geocode_{rounded_lat:.6f}_{rounded_lng:.6f}"
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result

    try:
        throttle_nominatim_request()
        response = requests.get(
            NOMINATIM_REVERSE_URL,
            params={
                "format": "jsonv2",
                "lat": f"{rounded_lat:.6f}",
                "lon": f"{rounded_lng:.6f}",
                "zoom": 18,
                "addressdetails": 1,
            },
            headers={"User-Agent": NOMINATIM_USER_AGENT},
            timeout=6,
        )
        response.raise_for_status()
        data = response.json()
        formatted = format_location_name(data)
        if not formatted["display_name"] and not formatted["short_name"]:
            raise ValueError("No readable location returned.")
        result = {
            "success": True,
            "display_name": formatted["display_name"],
            "short_name": formatted["short_name"],
            "latitude": rounded_lat,
            "longitude": rounded_lng,
            "attribution": "Location data from OpenStreetMap contributors via Nominatim.",
        }
        cache.set(cache_key, result, timeout=GEOCODE_CACHE_SECONDS)
        return result
    except (requests.RequestException, ValueError):
        result = {
            "success": False,
            "message": "Location name unavailable. You can type the landmark manually.",
            "latitude": rounded_lat,
            "longitude": rounded_lng,
        }
        cache.set(cache_key, result, timeout=300)
        return result
