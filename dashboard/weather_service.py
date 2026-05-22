from collections import OrderedDict
from datetime import datetime, timezone

import requests
from django.conf import settings
from django.core.cache import cache


DEFAULT_LOCATION = "Tiniguiban, Puerto Princesa City"
DEFAULT_LAT = 9.7786
DEFAULT_LON = 118.7353

WEATHER_ICON_BY_MAIN = {
    "Thunderstorm": "bi-cloud-lightning-rain",
    "Drizzle": "bi-cloud-drizzle",
    "Rain": "bi-cloud-rain-heavy",
    "Snow": "bi-cloud-snow",
    "Mist": "bi-cloud-fog",
    "Smoke": "bi-cloud-fog",
    "Haze": "bi-cloud-fog",
    "Dust": "bi-cloud-fog",
    "Fog": "bi-cloud-fog",
    "Sand": "bi-cloud-fog",
    "Ash": "bi-cloud-fog",
    "Squall": "bi-wind",
    "Tornado": "bi-tornado",
    "Clear": "bi-brightness-high",
    "Clouds": "bi-cloud-sun",
}

SAMPLE_HOURLY = [
    {"label": "11 AM", "temperature": 33, "precipitation": 45, "wind": 8, "humidity": 72},
    {"label": "2 PM", "temperature": 32, "precipitation": 52, "wind": 9, "humidity": 73},
    {"label": "5 PM", "temperature": 31, "precipitation": 58, "wind": 8, "humidity": 76},
    {"label": "8 PM", "temperature": 29, "precipitation": 49, "wind": 7, "humidity": 78},
    {"label": "11 PM", "temperature": 28, "precipitation": 40, "wind": 6, "humidity": 80},
    {"label": "2 AM", "temperature": 28, "precipitation": 34, "wind": 6, "humidity": 81},
    {"label": "5 AM", "temperature": 28, "precipitation": 30, "wind": 5, "humidity": 82},
    {"label": "8 AM", "temperature": 29, "precipitation": 35, "wind": 7, "humidity": 78},
]

SAMPLE_FORECAST = [
    {"weekday": "Fri", "main": "Thunderstorm", "condition": "Scattered thunderstorms", "icon": "bi-cloud-lightning-rain", "icon_url": "https://openweathermap.org/img/wn/11d@2x.png", "temp_max": 33, "temp_min": 28, "precipitation": 45},
    {"weekday": "Sat", "main": "Thunderstorm", "condition": "Scattered thunderstorms", "icon": "bi-cloud-lightning-rain", "icon_url": "https://openweathermap.org/img/wn/11d@2x.png", "temp_max": 33, "temp_min": 27, "precipitation": 52},
    {"weekday": "Sun", "main": "Thunderstorm", "condition": "Thunderstorms", "icon": "bi-cloud-lightning-rain", "icon_url": "https://openweathermap.org/img/wn/11d@2x.png", "temp_max": 32, "temp_min": 27, "precipitation": 58},
    {"weekday": "Mon", "main": "Rain", "condition": "Rain", "icon": "bi-cloud-rain-heavy", "icon_url": "https://openweathermap.org/img/wn/10d@2x.png", "temp_max": 30, "temp_min": 27, "precipitation": 63},
    {"weekday": "Tue", "main": "Rain", "condition": "Rain showers", "icon": "bi-cloud-rain", "icon_url": "https://openweathermap.org/img/wn/09d@2x.png", "temp_max": 32, "temp_min": 27, "precipitation": 49},
    {"weekday": "Wed", "main": "Rain", "condition": "Cloudy with rain", "icon": "bi-cloud-drizzle", "icon_url": "https://openweathermap.org/img/wn/09d@2x.png", "temp_max": 32, "temp_min": 27, "precipitation": 44},
    {"weekday": "Thu", "main": "Rain", "condition": "Cloudy with rain", "icon": "bi-cloud-drizzle", "icon_url": "https://openweathermap.org/img/wn/09d@2x.png", "temp_max": 33, "temp_min": 27, "precipitation": 42},
    {"weekday": "Fri", "main": "Clouds", "condition": "Partly cloudy", "icon": "bi-cloud-sun", "icon_url": "https://openweathermap.org/img/wn/02d@2x.png", "temp_max": 32, "temp_min": 27, "precipitation": 28},
]


def get_weather_data(lat=DEFAULT_LAT, lon=DEFAULT_LON, location_name=DEFAULT_LOCATION):
    """
    Fetch weather dashboard data through OpenWeatherMap without exposing the API
    key to the browser. Falls back to sample SafeWalk data when the API is not
    reachable so the landing dashboard still renders professionally.
    """
    api_key = settings.OPENWEATHER_API_KEY
    cache_key = f"weather_dashboard_{round(float(lat), 3)}_{round(float(lon), 3)}"
    cached_weather = cache.get(cache_key)
    if cached_weather:
        return cached_weather

    if not api_key:
        return sample_weather_data(location_name)

    try:
        current = _fetch_openweather(
            "https://api.openweathermap.org/data/2.5/weather",
            {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
        )
        forecast = _fetch_openweather(
            "https://api.openweathermap.org/data/2.5/forecast",
            {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
        )
        weather = _build_weather_dashboard(current, forecast, location_name)
    except Exception:
        weather = sample_weather_data(location_name)

    cache.set(cache_key, weather, 900)
    return weather


def calculate_weather_walking_risk(weather_data):
    current = weather_data.get("current", weather_data)
    temp = current.get("temp", weather_data.get("temp", 0)) or 0
    precipitation = current.get("precipitation", weather_data.get("precipitation", 0)) or 0
    humidity = current.get("humidity", weather_data.get("humidity", 0)) or 0
    wind = current.get("wind", weather_data.get("wind", 0)) or 0
    main = current.get("main", weather_data.get("main", "Clear"))
    weather_code = current.get("weather_code", weather_data.get("weather_code", 800)) or 800

    is_thunderstorm = main == "Thunderstorm" or 200 <= int(weather_code) <= 232
    is_rain = main in {"Rain", "Drizzle"} or 300 <= int(weather_code) <= 531
    is_poor_visibility = main in {"Mist", "Smoke", "Haze", "Dust", "Fog", "Sand", "Ash"}

    level = "Low"
    title = "Safe Walking Weather"
    alert_type = "safe"
    message = "Weather is generally safe for walking. Stay aware of nearby safety reports."
    advice = "Use your normal route, stay alert at crossings, and check active SafeWalk reports nearby."
    reasons = ["normal temperature", "low rain risk"]

    if temp >= 36 or (is_thunderstorm and precipitation >= 80) or wind >= 50:
        level = "Critical"
        title = "Critical Weather Risk"
        alert_type = "danger"
        message = "Unsafe walking weather is likely in this area."
        advice = "Avoid walking if possible. Wait for conditions to improve and use only well-lit, sheltered routes for urgent trips."
        reasons = ["extreme heat or severe storm conditions"]
    elif is_thunderstorm:
        level = "High"
        title = "Thunderstorm Watch"
        alert_type = "danger"
        message = "Thunderstorms can create lightning, flooding, and poor visibility hazards."
        advice = "Delay non-essential walks. Avoid open areas, flood-prone shortcuts, and poorly lit roads."
        reasons = ["thunderstorm risk", "possible lightning"]
    elif temp >= 33 and humidity >= 70:
        level = "High"
        title = "Excessive Heat"
        alert_type = "danger"
        message = "Severe heat is expected in this area."
        advice = "Avoid long walks during peak heat. Bring water, use shaded routes, and avoid flood-prone shortcuts if rain starts."
        reasons = ["high heat", "high humidity"]
    elif temp >= 33 or precipitation >= 70 or is_rain:
        level = "Medium"
        title = "Weather Caution"
        alert_type = "caution"
        message = "Weather may make some walking routes less safe."
        advice = "Bring rain protection or water, choose shaded and well-drained routes, and avoid slippery sidewalks."
        reasons = ["heat, rain, or slippery-route risk"]
    elif wind >= 30 or is_poor_visibility or precipitation >= 45:
        level = "Medium"
        title = "Walking Caution"
        alert_type = "caution"
        message = "Wind, visibility, or rain chance may affect walking comfort and safety."
        advice = "Use well-lit routes, keep distance from traffic, and avoid exposed crossings."
        reasons = ["wind, visibility, or rain chance"]

    return {
        "level": level,
        "title": title,
        "type": alert_type,
        "message": message,
        "advice": advice,
        "reasons": reasons,
    }


def sample_weather_data(location_name=DEFAULT_LOCATION):
    weather = {
        "source": "sample",
        "location": location_name or DEFAULT_LOCATION,
        "current": {
            "temp": 33,
            "condition": "Scattered thunderstorms",
            "main": "Thunderstorm",
            "weather_code": 200,
            "precipitation": 45,
            "humidity": 72,
            "wind": 8,
            "icon": "bi-cloud-lightning-rain",
            "icon_url": "https://openweathermap.org/img/wn/11d@4x.png",
            "day": "Friday",
            "updated": "Updated recently",
        },
        "hourly": SAMPLE_HOURLY,
        "forecast": SAMPLE_FORECAST,
    }
    risk = calculate_weather_walking_risk(weather)
    weather["alert"] = {
        "title": risk["title"],
        "type": risk["type"],
        "location": weather["location"],
        "time": "Updated recently",
        "message": risk["message"],
    }
    weather["walking_advice"] = {
        "risk_level": risk["level"],
        "advice": risk["advice"],
        "reasons": risk["reasons"],
    }
    return _with_legacy_weather_keys(weather)


def _fetch_openweather(url, params):
    response = requests.get(url, params=params, timeout=8)
    response.raise_for_status()
    return response.json()


def _build_weather_dashboard(current, forecast, location_name):
    current_weather = (current.get("weather") or [{}])[0]
    main_data = current.get("main") or {}
    wind_data = current.get("wind") or {}
    forecast_items = forecast.get("list") or []
    city = forecast.get("city") or {}
    timezone_offset = city.get("timezone", 0)
    location = location_name or _format_location(current, city)
    current_precipitation = _forecast_pop(forecast_items[0]) if forecast_items else _current_precipitation(current)

    weather = {
        "source": "openweather",
        "location": location,
        "current": {
            "temp": round(main_data.get("temp", 0)),
            "condition": str(current_weather.get("description", "Weather")).title(),
            "main": current_weather.get("main", "Clear"),
            "weather_code": current_weather.get("id", 800),
            "precipitation": current_precipitation,
            "humidity": round(main_data.get("humidity", 0)),
            "wind": round(wind_data.get("speed", 0) * 3.6),
            "icon": _weather_icon(current_weather.get("main", "Clear"), current_weather.get("id", 800)),
            "icon_url": _openweather_icon_url(current_weather.get("icon"), size="4x"),
            "day": _weekday_from_timestamp(current.get("dt"), timezone_offset, long=True),
            "updated": _updated_time(current.get("dt"), timezone_offset),
        },
        "hourly": _hourly_forecast(forecast_items, timezone_offset),
        "forecast": _daily_forecast(forecast_items, timezone_offset),
    }

    risk = calculate_weather_walking_risk(weather)
    weather["alert"] = {
        "title": risk["title"],
        "type": risk["type"],
        "location": location,
        "time": weather["current"]["updated"],
        "message": risk["message"],
    }
    weather["walking_advice"] = {
        "risk_level": risk["level"],
        "advice": risk["advice"],
        "reasons": risk["reasons"],
    }
    return _with_legacy_weather_keys(weather)


def _hourly_forecast(items, timezone_offset):
    points = []
    for item in items[:8]:
        main = item.get("main") or {}
        wind = item.get("wind") or {}
        points.append(
            {
                "label": _hour_label(item.get("dt"), timezone_offset),
                "temperature": round(main.get("temp", 0)),
                "precipitation": _forecast_pop(item),
                "wind": round(wind.get("speed", 0) * 3.6),
                "humidity": round(main.get("humidity", 0)),
            }
        )
    return points or SAMPLE_HOURLY


def _daily_forecast(items, timezone_offset):
    grouped = OrderedDict()
    for item in items:
        date_key = _date_key(item.get("dt"), timezone_offset)
        grouped.setdefault(date_key, []).append(item)

    days = []
    for date_key, day_items in grouped.items():
        max_temp = max((entry.get("main") or {}).get("temp_max", 0) for entry in day_items)
        min_temp = min((entry.get("main") or {}).get("temp_min", 0) for entry in day_items)
        representative = max(day_items, key=lambda entry: _forecast_pop(entry))
        weather = (representative.get("weather") or [{}])[0]
        days.append(
            {
                "weekday": _weekday_from_date_key(date_key),
                "main": weather.get("main", "Clear"),
                "condition": str(weather.get("description", "Weather")).title(),
                "icon": _weather_icon(weather.get("main", "Clear"), weather.get("id", 800)),
                "icon_url": _openweather_icon_url(weather.get("icon"), size="2x"),
                "temp_max": round(max_temp),
                "temp_min": round(min_temp),
                "precipitation": max(_forecast_pop(entry) for entry in day_items),
            }
        )

    if len(days) < 8:
        days.extend(SAMPLE_FORECAST[len(days):])
    return days[:8] or SAMPLE_FORECAST


def _forecast_pop(item):
    return round(float(item.get("pop", 0)) * 100)


def _current_precipitation(current):
    rain = (current.get("rain") or {}).get("1h", 0)
    snow = (current.get("snow") or {}).get("1h", 0)
    return 80 if rain or snow else 0


def _weather_icon(main, weather_code):
    if 200 <= int(weather_code or 800) <= 232:
        return "bi-cloud-lightning-rain"
    return WEATHER_ICON_BY_MAIN.get(main, "bi-cloud-sun")


def _openweather_icon_url(icon_code, size="2x"):
    if not icon_code:
        return ""
    return f"https://openweathermap.org/img/wn/{icon_code}@{size}.png"


def _format_location(current, city):
    name = current.get("name") or city.get("name") or DEFAULT_LOCATION
    country = (current.get("sys") or {}).get("country") or city.get("country")
    return f"{name}, {country}" if country and country not in name else name


def _local_datetime(timestamp, timezone_offset):
    if not timestamp:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(int(timestamp) + int(timezone_offset or 0), timezone.utc)


def _weekday_from_timestamp(timestamp, timezone_offset, long=False):
    fmt = "%A" if long else "%a"
    return _local_datetime(timestamp, timezone_offset).strftime(fmt)


def _weekday_from_date_key(date_key):
    try:
        return datetime.strptime(date_key, "%Y-%m-%d").strftime("%a")
    except ValueError:
        return "Day"


def _date_key(timestamp, timezone_offset):
    return _local_datetime(timestamp, timezone_offset).strftime("%Y-%m-%d")


def _hour_label(timestamp, timezone_offset):
    label = _local_datetime(timestamp, timezone_offset).strftime("%I %p")
    return label.lstrip("0")


def _updated_time(timestamp, timezone_offset):
    if not timestamp:
        return "Updated recently"
    return f"Updated {_local_datetime(timestamp, timezone_offset).strftime('%I:%M %p').lstrip('0')}"


def _with_legacy_weather_keys(weather):
    current = weather["current"]
    weather.update(
        {
            "temp": current["temp"],
            "description": current["condition"],
            "icon": "01d",
            "main": current["main"],
            "risk_level": weather["walking_advice"]["risk_level"],
            "advice": weather["walking_advice"]["advice"],
        }
    )
    return weather
