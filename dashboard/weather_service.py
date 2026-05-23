from collections import OrderedDict
from datetime import datetime, timedelta, timezone

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
    {"weekday": "Fri", "main": "Clear", "condition": "Sunny", "icon": "bi-brightness-high", "icon_url": "https://openweathermap.org/img/wn/01d@2x.png", "temp_max": 35, "temp_min": 27, "precipitation": 5},
    {"weekday": "Sat", "main": "Clear", "condition": "Sunny", "icon": "bi-brightness-high", "icon_url": "https://openweathermap.org/img/wn/01d@2x.png", "temp_max": 36, "temp_min": 27, "precipitation": 2},
    {"weekday": "Sun", "main": "Clouds", "condition": "Partly cloudy", "icon": "bi-cloud-sun", "icon_url": "https://openweathermap.org/img/wn/02d@2x.png", "temp_max": 34, "temp_min": 26, "precipitation": 15},
    {"weekday": "Mon", "main": "Clouds", "condition": "Cloudy", "icon": "bi-cloud", "icon_url": "https://openweathermap.org/img/wn/03d@2x.png", "temp_max": 33, "temp_min": 26, "precipitation": 20},
    {"weekday": "Tue", "main": "Rain", "condition": "Light rain", "icon": "bi-cloud-rain", "icon_url": "https://openweathermap.org/img/wn/10d@2x.png", "temp_max": 31, "temp_min": 25, "precipitation": 45},
    {"weekday": "Wed", "main": "Rain", "condition": "Showers", "icon": "bi-cloud-drizzle", "icon_url": "https://openweathermap.org/img/wn/09d@2x.png", "temp_max": 30, "temp_min": 25, "precipitation": 55},
    {"weekday": "Thu", "main": "Thunderstorm", "condition": "Thunderstorm", "icon": "bi-cloud-lightning-rain", "icon_url": "https://openweathermap.org/img/wn/11d@2x.png", "temp_max": 29, "temp_min": 24, "precipitation": 80},
    {"weekday": "Fri", "main": "Clear", "condition": "Sunny", "icon": "bi-brightness-high", "icon_url": "https://openweathermap.org/img/wn/01d@2x.png", "temp_max": 32, "temp_min": 26, "precipitation": 10},
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


def calculate_weather_safety_index(weather_data):
    current = weather_data.get("current", weather_data)
    temp = round(current.get("temp", current.get("temperature", weather_data.get("temp", 0))) or 0)
    rain_probability = round(current.get("precipitation", current.get("rain_probability", weather_data.get("precipitation", 0))) or 0)
    humidity = round(current.get("humidity", weather_data.get("humidity", 0)) or 0)
    wind_speed = round(current.get("wind", current.get("wind_speed", weather_data.get("wind", 0))) or 0)
    main = current.get("main", weather_data.get("main", "Clear")) or "Clear"
    condition = current.get("condition", weather_data.get("condition", main)) or main
    weather_code = int(current.get("weather_code", weather_data.get("weather_code", 800)) or 800)
    visibility = current.get("visibility", weather_data.get("visibility"))

    is_thunderstorm = main == "Thunderstorm" or 200 <= weather_code <= 232 or "thunder" in condition.lower()
    is_poor_visibility = (
        main in {"Mist", "Smoke", "Haze", "Dust", "Fog", "Sand", "Ash"}
        or (visibility is not None and float(visibility) < 3000)
    )

    probability = 0
    reasons = []
    if rain_probability > 70:
        probability += 35
        reasons.append(f"Rain probability {rain_probability}%")
    elif rain_probability > 40:
        probability += 20
        reasons.append(f"Rain probability {rain_probability}%")
    if is_thunderstorm:
        probability += 30
        reasons.append(condition)
    if temp >= 36:
        probability += 35
        reasons.append(f"High temperature {temp}C")
    elif temp >= 33:
        probability += 20
        reasons.append(f"High temperature {temp}C")
    if wind_speed > 35:
        probability += 30
        reasons.append(f"Strong wind {wind_speed} km/h")
    elif wind_speed > 20:
        probability += 15
        reasons.append(f"Wind {wind_speed} km/h")
    if humidity > 75:
        probability += 10
        reasons.append(f"Humidity {humidity}%")
    if is_poor_visibility:
        probability += 20
        reasons.append("Poor visibility")

    probability = max(0, min(100, probability))
    if probability <= 20:
        label = "Safe"
        risk_key = "safe"
        advice = "Good walking condition. Stay aware of traffic and nearby SafeWalk reports."
    elif probability <= 40:
        label = "Low Risk"
        risk_key = "low"
        advice = "Minor weather concern. Use normal walking precautions."
    elif probability <= 60:
        label = "Moderate Risk"
        risk_key = "moderate"
        advice = "Use caution while walking. Bring rain protection or water if needed."
    elif probability <= 80:
        label = "High Risk"
        risk_key = "high"
        advice = "Walking may be unsafe in exposed or poorly lit areas. Use visible main roads."
    else:
        label = "Critical Risk"
        risk_key = "critical"
        advice = "Avoid walking if possible. Wait for conditions to improve."

    if not reasons:
        reasons = ["Weather conditions are generally favorable."]

    return {
        "index_label": label,
        "index_probability": probability,
        "index_key": risk_key,
        "advice": advice,
        "risk_reasons": reasons,
    }


def calculate_weather_walking_risk(weather_data):
    current = weather_data.get("current", weather_data)
    temp = current.get("temp", weather_data.get("temp", 0)) or 0
    precipitation = current.get("precipitation", weather_data.get("precipitation", 0)) or 0
    humidity = current.get("humidity", weather_data.get("humidity", 0)) or 0
    wind = current.get("wind", weather_data.get("wind", 0)) or 0
    main = current.get("main", weather_data.get("main", "Clear"))
    weather_code = current.get("weather_code", weather_data.get("weather_code", 800)) or 800

    # Basic Heat Index approximation for safety intelligence
    heat_index = temp
    if temp >= 27 and humidity >= 40:
        # Simplified heat index logic
        heat_index = temp + (0.55 * (humidity / 100) * (temp - 14.5))

    is_thunderstorm = main == "Thunderstorm" or 200 <= int(weather_code) <= 232
    is_rain = main in {"Rain", "Drizzle"} or 300 <= int(weather_code) <= 531
    is_poor_visibility = main in {"Mist", "Smoke", "Haze", "Dust", "Fog", "Sand", "Ash"}

    level = "Low"
    title = "Safe Walking Weather"
    alert_type = "safe"
    message = "Weather is generally safe for walking. Stay aware of nearby safety reports."
    advice = "Use your normal route, stay alert at crossings, and check active SafeWalk reports nearby."
    reasons = ["Normal temperature", "Low environmental risk"]

    # PRIORITY 1: CRITICAL RISKS
    if heat_index >= 41 or temp >= 38:
        level = "Critical"
        title = "Extreme Heat Warning"
        alert_type = "danger"
        message = "Dangerously high temperatures detected. Heat stroke risk is extremely high."
        advice = "Avoid all outdoor activity. If you must walk, stay in air-conditioned areas as much as possible."
        reasons = ["Extreme heat index"]
    elif (is_thunderstorm and precipitation >= 80) or wind >= 60:
        level = "Critical"
        title = "Severe Storm Warning"
        alert_type = "danger"
        message = "Life-threatening storm conditions are likely."
        advice = "Seek immediate sturdy shelter. Do not attempt to walk through flooded areas or under trees."
        reasons = ["Severe storm/wind conditions"]
    
    # PRIORITY 2: HIGH RISKS
    elif heat_index >= 35 or temp >= 35:
        level = "High"
        title = "Excessive Heat"
        alert_type = "danger"
        message = "Severe heat is expected. Prolonged outdoor exposure is dangerous."
        advice = "Avoid long walks during peak heat (10 AM - 4 PM). Bring water and stick to shaded routes."
        reasons = ["High temperature/humidity"]
    elif is_thunderstorm:
        level = "High"
        title = "Thunderstorm Watch"
        alert_type = "danger"
        message = "Thunderstorms can create lightning, flooding, and poor visibility hazards."
        advice = "Delay non-essential walks. Avoid open areas and poorly lit roads."
        reasons = ["Thunderstorm risk"]

    # PRIORITY 3: MEDIUM RISKS
    elif temp >= 32 or precipitation >= 70 or is_rain:
        level = "Medium"
        title = "Weather Caution"
        alert_type = "caution"
        message = "Weather may make some walking routes less comfortable or safe."
        advice = "Bring rain protection or extra water, and choose well-drained routes."
        reasons = ["Moderate heat/rain risk"]
    elif wind >= 30 or is_poor_visibility or precipitation >= 40:
        level = "Medium"
        title = "Walking Caution"
        alert_type = "caution"
        message = "Wind or visibility may affect walking comfort."
        advice = "Stay on well-lit paths and keep distance from heavy traffic."
        reasons = ["Wind/visibility risk"]

    return {
        "level": level,
        "title": title,
        "type": alert_type,
        "message": message,
        "advice": advice,
        "reasons": reasons,
    }


def sample_weather_data(location_name=DEFAULT_LOCATION):
    now = datetime.now()
    weather = {
        "source": "sample",
        "location": location_name or DEFAULT_LOCATION,
        "current": {
            "temp": 34,
            "condition": "Mostly Sunny",
            "main": "Clear",
            "weather_code": 800,
            "precipitation": 5,
            "humidity": 65,
            "wind": 12,
            "icon": "bi-brightness-high",
            "icon_url": "https://openweathermap.org/img/wn/01d@4x.png",
            "day": "Friday",
            "date": _format_display_date(now),
            "date_short": _format_display_date(now, short=True),
            "updated": "Updated recently",
        },
        "hourly": SAMPLE_HOURLY,
        "forecast": SAMPLE_FORECAST,
    }
    _enrich_weather_indexes(weather)
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
            "visibility": current.get("visibility"),
            "icon": _weather_icon(current_weather.get("main", "Clear"), current_weather.get("id", 800)),
            "icon_url": _openweather_icon_url(current_weather.get("icon"), size="4x"),
            "day": _weekday_from_timestamp(current.get("dt"), timezone_offset, long=True),
            "date": _date_from_timestamp(current.get("dt"), timezone_offset),
            "date_short": _date_from_timestamp(current.get("dt"), timezone_offset, short=True),
            "updated": _updated_time(current.get("dt"), timezone_offset),
        },
        "hourly": _hourly_forecast(forecast_items, timezone_offset),
        "forecast": _daily_forecast(forecast_items, timezone_offset),
    }

    _enrich_weather_indexes(weather)
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
        humidity_values = [(entry.get("main") or {}).get("humidity", 0) for entry in day_items]
        wind_values = [(entry.get("wind") or {}).get("speed", 0) * 3.6 for entry in day_items]
        days.append(
            {
                "weekday": _weekday_from_date_key(date_key),
                "day": _weekday_from_date_key(date_key, long=True),
                "date": _formatted_date_key(date_key),
                "date_short": _formatted_date_key(date_key, short=True),
                "date_key": date_key,
                "main": weather.get("main", "Clear"),
                "weather_code": weather.get("id", 800),
                "condition": str(weather.get("description", "Weather")).title(),
                "icon": _weather_icon(weather.get("main", "Clear"), weather.get("id", 800)),
                "icon_url": _openweather_icon_url(weather.get("icon"), size="2x"),
                "temp_max": round(max_temp),
                "temp_min": round(min_temp),
                "temperature": round(max_temp),
                "precipitation": max(_forecast_pop(entry) for entry in day_items),
                "rain_probability": max(_forecast_pop(entry) for entry in day_items),
                "humidity": round(sum(humidity_values) / len(humidity_values)) if humidity_values else 0,
                "wind": round(max(wind_values)) if wind_values else 0,
                "wind_speed": round(max(wind_values)) if wind_values else 0,
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


def _weekday_from_date_key(date_key, long=False):
    try:
        return datetime.strptime(date_key, "%Y-%m-%d").strftime("%A" if long else "%a")
    except ValueError:
        return "Day"


def _formatted_date_key(date_key, short=False):
    try:
        return _format_display_date(datetime.strptime(date_key, "%Y-%m-%d"), short=short)
    except ValueError:
        return date_key


def _date_from_timestamp(timestamp, timezone_offset, short=False):
    return _format_display_date(_local_datetime(timestamp, timezone_offset), short=short)


def _format_display_date(value, short=False):
    return f"{value.strftime('%b' if short else '%B')} {value.day}" if short else f"{value.strftime('%B')} {value.day}, {value.year}"


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
    _enrich_weather_indexes(weather)
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


def _enrich_weather_indexes(weather):
    current = weather.get("current", {})
    current_index = calculate_weather_safety_index({"current": current})
    current.update(current_index)
    current["rain_probability"] = current.get("precipitation", 0)
    current["wind_speed"] = current.get("wind", 0)
    weather["weather_today"] = current

    enriched = []
    base_date = datetime.now()
    for index, day in enumerate(weather.get("forecast", [])):
        if "date" not in day:
            forecast_date = base_date + timedelta(days=index)
            day["day"] = forecast_date.strftime("%A")
            day["date"] = _format_display_date(forecast_date)
            day["date_short"] = _format_display_date(forecast_date, short=True)
        day["temperature"] = day.get("temperature", day.get("temp_max", 0))
        day["high"] = day.get("temp_max", day.get("high", day.get("temperature", 0)))
        day["low"] = day.get("temp_min", day.get("low", day.get("temperature", 0)))
        day["rain_probability"] = day.get("rain_probability", day.get("precipitation", 0))
        day["humidity"] = day.get("humidity", current.get("humidity", 0))
        day["wind_speed"] = day.get("wind_speed", day.get("wind", current.get("wind", 0)))
        day.update(calculate_weather_safety_index({"current": day}))
        day["is_today"] = index == 0
        enriched.append(day)
    weather["daily_forecast"] = enriched
    weather["forecast"] = enriched
    return weather
