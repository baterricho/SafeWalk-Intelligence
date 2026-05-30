import math
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
    Fetch weather dashboard data. Tries OpenWeatherMap first if an API key is
    configured, then falls back to Open-Meteo (free, no key needed). Uses sample
    SafeWalk data as a last resort so the dashboard always renders.
    """
    api_key = settings.OPENWEATHER_API_KEY
    cache_key = f"weather_dashboard_{round(float(lat), 3)}_{round(float(lon), 3)}"
    cached_weather = cache.get(cache_key)
    if cached_weather:
        return cached_weather

    weather = None

    # Try OpenWeatherMap first if API key is available
    if api_key:
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
            weather = None

    # Fallback to Open-Meteo (free, no API key)
    if weather is None:
        try:
            open_meteo_data = _fetch_open_meteo(lat, lon)
            weather = _build_open_meteo_dashboard(open_meteo_data, location_name)
        except Exception:
            weather = sample_weather_data(location_name)

    cache.set(cache_key, weather, 600)
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
    is_poor_visibility = main in {"Mist", "Smoke", "Haze", "Dust", "Fog", "Sand", "Ash"}
    if visibility is not None:
        visibility_value = float(visibility)
        visibility_threshold = 3 if visibility_value <= 100 else 3000
        is_poor_visibility = is_poor_visibility or visibility_value < visibility_threshold

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
    if probability < 20:
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


def _alert_from_safety_index(weather):
    current = weather.get("weather_today") or weather.get("current", {})
    safety_index = current if current.get("index_label") else calculate_weather_safety_index({"current": current})
    index_key = safety_index.get("index_key", "safe")
    title = "Safe Walking Weather" if index_key == "safe" else f"{safety_index.get('index_label', 'Weather')} Weather"
    message = "; ".join(safety_index.get("risk_reasons", [])) or "Check conditions before walking."
    alert_type = "danger" if index_key in {"high", "critical"} else "caution" if index_key == "moderate" else "safe"

    return {
        "title": title,
        "type": alert_type,
        "location": weather.get("location", DEFAULT_LOCATION),
        "time": weather.get("current", {}).get("updated", "Updated recently"),
        "message": message,
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
            "day": now.strftime("%A"),
            "date": _format_display_date(now),
            "date_short": _format_display_date(now, short=True),
            "updated": "Updated recently",
            "feels_like": 37,
            "uv_index": 7,
            "pressure": 1010,
            "visibility": 10.0,
            "dew_point": 25,
            "sunrise": "5:42 AM",
            "sunset": "6:15 PM",
        },
        "hourly": SAMPLE_HOURLY,
        "forecast": SAMPLE_FORECAST,
    }
    _enrich_weather_indexes(weather)
    weather["alert"] = _alert_from_safety_index(weather)
    risk = calculate_weather_walking_risk(weather)
    weather["walking_advice"] = {
        "risk_level": risk["level"],
        "advice": weather["weather_today"].get("advice", risk["advice"]),
        "reasons": risk["reasons"],
    }
    return _with_legacy_weather_keys(weather)


def _fetch_openweather(url, params):
    response = requests.get(url, params=params, timeout=8)
    response.raise_for_status()
    return response.json()


def _fetch_open_meteo(lat, lon):
    """Fetch weather data from Open-Meteo (free, no API key required)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,surface_pressure,is_day",
        "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,relative_humidity_2m,apparent_temperature,uv_index,visibility,dew_point_2m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max,sunrise,sunset,uv_index_max,apparent_temperature_max,apparent_temperature_min",
        "timezone": "auto",
        "forecast_days": "7",
    }
    response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def _calculate_dew_point(temp, humidity):
    """Calculate dew point using the Magnus formula."""
    if humidity <= 0:
        return 0
    a = 17.27
    b = 237.7
    alpha = (a * temp) / (b + temp) + math.log(humidity / 100.0)
    return round(b * alpha / (a - alpha))


def _build_weather_dashboard(current, forecast, location_name):
    current_weather = (current.get("weather") or [{}])[0]
    main_data = current.get("main") or {}
    wind_data = current.get("wind") or {}
    forecast_items = forecast.get("list") or []
    city = forecast.get("city") or {}
    timezone_offset = city.get("timezone", 0)
    location = location_name or _format_location(current, city)
    current_precipitation = _forecast_pop(forecast_items[0]) if forecast_items else _current_precipitation(current)

    temp = round(main_data.get("temp", 0))
    humidity = round(main_data.get("humidity", 0))
    raw_visibility = current.get("visibility", 10000)
    sunrise_ts = (current.get("sys") or {}).get("sunrise")
    sunset_ts = (current.get("sys") or {}).get("sunset")

    weather = {
        "source": "openweather",
        "location": location,
        "current": {
            "temp": temp,
            "condition": str(current_weather.get("description", "Weather")).title(),
            "main": current_weather.get("main", "Clear"),
            "weather_code": current_weather.get("id", 800),
            "precipitation": current_precipitation,
            "humidity": humidity,
            "wind": round(wind_data.get("speed", 0) * 3.6),
            "visibility": round(raw_visibility / 1000, 1) if raw_visibility else 10.0,
            "icon": _weather_icon(current_weather.get("main", "Clear"), current_weather.get("id", 800)),
            "icon_url": _openweather_icon_url(current_weather.get("icon"), size="4x"),
            "day": _weekday_from_timestamp(current.get("dt"), timezone_offset, long=True),
            "date": _date_from_timestamp(current.get("dt"), timezone_offset),
            "date_short": _date_from_timestamp(current.get("dt"), timezone_offset, short=True),
            "updated": _updated_time(current.get("dt"), timezone_offset),
            "feels_like": round(main_data.get("feels_like", 0)),
            "uv_index": 0,  # OpenWeather free tier doesn't include UV in basic endpoint
            "pressure": round(main_data.get("pressure", 0)),
            "dew_point": _calculate_dew_point(temp, humidity),
            "sunrise": _format_timestamp_time(sunrise_ts, timezone_offset) if sunrise_ts else "",
            "sunset": _format_timestamp_time(sunset_ts, timezone_offset) if sunset_ts else "",
        },
        "hourly": _hourly_forecast(forecast_items, timezone_offset),
        "forecast": _daily_forecast(forecast_items, timezone_offset),
    }

    _enrich_weather_indexes(weather)
    weather["alert"] = _alert_from_safety_index(weather)
    risk = calculate_weather_walking_risk(weather)
    weather["walking_advice"] = {
        "risk_level": risk["level"],
        "advice": weather["weather_today"].get("advice", risk["advice"]),
        "reasons": risk["reasons"],
    }
    return _with_legacy_weather_keys(weather)


# ---------- WMO weather-code mapping (Open-Meteo) ----------

WMO_CODE_MAP = {
    0: ("Clear sky", "Clear", "bi-brightness-high"),
    1: ("Mainly clear", "Clear", "bi-brightness-high"),
    2: ("Partly cloudy", "Clouds", "bi-cloud-sun"),
    3: ("Overcast", "Clouds", "bi-cloud"),
    45: ("Fog", "Fog", "bi-cloud-fog"),
    48: ("Depositing rime fog", "Fog", "bi-cloud-fog"),
    51: ("Light drizzle", "Drizzle", "bi-cloud-drizzle"),
    53: ("Moderate drizzle", "Drizzle", "bi-cloud-drizzle"),
    55: ("Dense drizzle", "Drizzle", "bi-cloud-drizzle"),
    56: ("Light freezing drizzle", "Drizzle", "bi-cloud-drizzle"),
    57: ("Dense freezing drizzle", "Drizzle", "bi-cloud-drizzle"),
    61: ("Slight rain", "Rain", "bi-cloud-rain"),
    63: ("Moderate rain", "Rain", "bi-cloud-rain-heavy"),
    65: ("Heavy rain", "Rain", "bi-cloud-rain-heavy"),
    66: ("Light freezing rain", "Rain", "bi-cloud-rain-heavy"),
    67: ("Heavy freezing rain", "Rain", "bi-cloud-rain-heavy"),
    71: ("Slight snow", "Snow", "bi-cloud-snow"),
    73: ("Moderate snow", "Snow", "bi-cloud-snow"),
    75: ("Heavy snow", "Snow", "bi-cloud-snow"),
    77: ("Snow grains", "Snow", "bi-cloud-snow"),
    80: ("Slight rain showers", "Rain", "bi-cloud-rain"),
    81: ("Moderate rain showers", "Rain", "bi-cloud-rain-heavy"),
    82: ("Violent rain showers", "Rain", "bi-cloud-rain-heavy"),
    85: ("Slight snow showers", "Snow", "bi-cloud-snow"),
    86: ("Heavy snow showers", "Snow", "bi-cloud-snow"),
    95: ("Thunderstorm", "Thunderstorm", "bi-cloud-lightning-rain"),
    96: ("Thunderstorm with slight hail", "Thunderstorm", "bi-cloud-lightning-rain"),
    99: ("Thunderstorm with heavy hail", "Thunderstorm", "bi-cloud-lightning-rain"),
}


def _wmo_decode(code):
    """Decode a WMO weather code into (condition, main, icon)."""
    return WMO_CODE_MAP.get(int(code or 0), ("Unknown", "Clear", "bi-cloud-sun"))


def _format_open_meteo_time(iso_str):
    """Format an Open-Meteo ISO time string like '2026-05-30T14:00' to '2 PM'."""
    try:
        dt = datetime.fromisoformat(iso_str)
        label = dt.strftime("%I %p").lstrip("0")
        return label
    except (ValueError, TypeError):
        return ""


def _format_open_meteo_sunrise_sunset(iso_str):
    """Format an Open-Meteo ISO time string to '5:42 AM' style."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%I:%M %p").lstrip("0")
    except (ValueError, TypeError):
        return ""


def _build_open_meteo_dashboard(data, location_name):
    """Normalize Open-Meteo response to the same format as the OpenWeather dashboard."""
    current_data = data.get("current", {})
    hourly_data = data.get("hourly", {})
    daily_data = data.get("daily", {})
    now = datetime.now()

    wmo_code = current_data.get("weather_code", 0)
    condition, main_weather, icon = _wmo_decode(wmo_code)
    temp = round(current_data.get("temperature_2m", 0))
    humidity = round(current_data.get("relative_humidity_2m", 0))
    wind = round(current_data.get("wind_speed_10m", 0))
    precip = round(current_data.get("precipitation", 0))
    feels_like = round(current_data.get("apparent_temperature", temp))
    pressure = round(current_data.get("surface_pressure", 0))
    is_day = current_data.get("is_day", 1)

    # Get sunrise/sunset from daily (first day)
    daily_sunrise = (daily_data.get("sunrise") or [""])[0]
    daily_sunset = (daily_data.get("sunset") or [""])[0]
    uv_max = (daily_data.get("uv_index_max") or [0])[0]

    # Hourly data - first 8 entries
    hourly_times = hourly_data.get("time", [])[:8]
    hourly_temps = hourly_data.get("temperature_2m", [])[:8]
    hourly_precip = hourly_data.get("precipitation_probability", [])[:8]
    hourly_wind = hourly_data.get("wind_speed_10m", [])[:8]
    hourly_humidity = hourly_data.get("relative_humidity_2m", [])[:8]
    hourly_uv = hourly_data.get("uv_index", [])[:8]
    hourly_vis = hourly_data.get("visibility", [])[:8]
    hourly_dew = hourly_data.get("dew_point_2m", [])[:8]

    hourly = []
    for i in range(min(8, len(hourly_times))):
        hourly.append({
            "label": _format_open_meteo_time(hourly_times[i]) if i < len(hourly_times) else "",
            "temperature": round(hourly_temps[i]) if i < len(hourly_temps) else 0,
            "precipitation": round(hourly_precip[i]) if i < len(hourly_precip) else 0,
            "wind": round(hourly_wind[i]) if i < len(hourly_wind) else 0,
            "humidity": round(hourly_humidity[i]) if i < len(hourly_humidity) else 0,
        })

    # Daily forecast - up to 7 days
    daily_times = daily_data.get("time", [])[:7]
    daily_codes = daily_data.get("weather_code", [])[:7]
    daily_max = daily_data.get("temperature_2m_max", [])[:7]
    daily_min = daily_data.get("temperature_2m_min", [])[:7]
    daily_precip_prob = daily_data.get("precipitation_probability_max", [])[:7]
    daily_wind_max = daily_data.get("wind_speed_10m_max", [])[:7]
    daily_uv_max_list = daily_data.get("uv_index_max", [])[:7]
    daily_feels_max = daily_data.get("apparent_temperature_max", [])[:7]
    daily_feels_min = daily_data.get("apparent_temperature_min", [])[:7]

    forecast = []
    for i in range(min(7, len(daily_times))):
        try:
            day_dt = datetime.strptime(daily_times[i], "%Y-%m-%d")
        except (ValueError, TypeError):
            day_dt = now + timedelta(days=i)
        day_cond, day_main, day_icon = _wmo_decode(daily_codes[i] if i < len(daily_codes) else 0)
        forecast.append({
            "weekday": day_dt.strftime("%a"),
            "day": day_dt.strftime("%A"),
            "date": _format_display_date(day_dt),
            "date_short": _format_display_date(day_dt, short=True),
            "date_key": day_dt.strftime("%Y-%m-%d"),
            "main": day_main,
            "weather_code": daily_codes[i] if i < len(daily_codes) else 0,
            "condition": day_cond,
            "icon": day_icon,
            "icon_url": "",
            "temp_max": round(daily_max[i]) if i < len(daily_max) else 0,
            "temp_min": round(daily_min[i]) if i < len(daily_min) else 0,
            "temperature": round(daily_max[i]) if i < len(daily_max) else 0,
            "precipitation": round(daily_precip_prob[i]) if i < len(daily_precip_prob) else 0,
            "rain_probability": round(daily_precip_prob[i]) if i < len(daily_precip_prob) else 0,
            "humidity": humidity,
            "wind": round(daily_wind_max[i]) if i < len(daily_wind_max) else 0,
            "wind_speed": round(daily_wind_max[i]) if i < len(daily_wind_max) else 0,
        })

    # Get first hourly visibility for current visibility
    current_visibility_m = hourly_vis[0] if hourly_vis else 10000
    current_dew = hourly_dew[0] if hourly_dew else _calculate_dew_point(temp, humidity)
    current_uv = hourly_uv[0] if hourly_uv else uv_max

    # Estimate precipitation probability from first hourly entry
    current_precip_prob = hourly_precip[0] if hourly_precip else (80 if precip > 0 else 0)

    weather = {
        "source": "open-meteo",
        "location": location_name or DEFAULT_LOCATION,
        "current": {
            "temp": temp,
            "condition": condition,
            "main": main_weather,
            "weather_code": wmo_code,
            "precipitation": current_precip_prob,
            "humidity": humidity,
            "wind": wind,
            "visibility": round(current_visibility_m / 1000, 1) if current_visibility_m else 10.0,
            "icon": icon,
            "icon_url": "",
            "day": now.strftime("%A"),
            "date": _format_display_date(now),
            "date_short": _format_display_date(now, short=True),
            "updated": f"Updated {now.strftime('%I:%M %p').lstrip('0')}",
            "feels_like": feels_like,
            "uv_index": round(current_uv, 1) if current_uv else 0,
            "pressure": pressure,
            "dew_point": round(current_dew) if current_dew else _calculate_dew_point(temp, humidity),
            "sunrise": _format_open_meteo_sunrise_sunset(daily_sunrise),
            "sunset": _format_open_meteo_sunrise_sunset(daily_sunset),
        },
        "hourly": hourly or SAMPLE_HOURLY,
        "forecast": forecast or SAMPLE_FORECAST,
    }

    _enrich_weather_indexes(weather)
    weather["alert"] = _alert_from_safety_index(weather)
    risk = calculate_weather_walking_risk(weather)
    weather["walking_advice"] = {
        "risk_level": risk["level"],
        "advice": weather["weather_today"].get("advice", risk["advice"]),
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


def _format_timestamp_time(timestamp, timezone_offset):
    """Format a Unix timestamp to a time string like '5:42 AM'."""
    if not timestamp:
        return ""
    dt = _local_datetime(timestamp, timezone_offset)
    return dt.strftime("%I:%M %p").lstrip("0")


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
            "feels_like": current.get("feels_like", 0),
            "uv_index": current.get("uv_index", 0),
            "pressure": current.get("pressure", 0),
            "visibility": current.get("visibility", 0),
            "dew_point": current.get("dew_point", 0),
            "sunrise": current.get("sunrise", ""),
            "sunset": current.get("sunset", ""),
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
            day["weekday"] = forecast_date.strftime("%a")
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
