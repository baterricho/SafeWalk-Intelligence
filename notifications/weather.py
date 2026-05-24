from datetime import time

from django.utils import timezone


PERIODS = {
    "morning": {
        "label": "Morning",
        "title": "Morning Weather Update",
        "start": time(5, 0),
        "end": time(10, 59, 59),
        "adverb": "this morning",
    },
    "afternoon": {
        "label": "Afternoon",
        "title": "Afternoon Weather Update",
        "start": time(11, 0),
        "end": time(17, 59, 59),
        "adverb": "this afternoon",
    },
    "evening": {
        "label": "Evening",
        "title": "Evening Weather Update",
        "start": time(18, 0),
        "end": time(22, 0),
        "adverb": "this evening",
    },
}


def current_weather_period(now=None):
    local_time = timezone.localtime(now or timezone.now()).time()
    for period, config in PERIODS.items():
        if config["start"] <= local_time <= config["end"]:
            return period
    if local_time < PERIODS["morning"]["start"]:
        return "morning"
    return "evening"


def period_title(period):
    return PERIODS.get(period, PERIODS["morning"])["title"]


def calculate_weather_alert(weather_data, period):
    current = weather_data.get("current", weather_data)
    temp = round(float(current.get("temp", current.get("temperature", 0)) or 0))
    rain_probability = round(float(current.get("precipitation", current.get("rain_probability", 0)) or 0))
    wind = round(float(current.get("wind", current.get("wind_speed", 0)) or 0))
    visibility = current.get("visibility")
    condition = str(current.get("condition", current.get("main", "Clear")) or "Clear")
    main = str(current.get("main", "Clear") or "Clear")
    weather_code = int(current.get("weather_code", 800) or 800)
    period_config = PERIODS.get(period, PERIODS["morning"])
    adverb = period_config["adverb"]

    is_thunderstorm = main == "Thunderstorm" or 200 <= weather_code <= 232 or "thunder" in condition.lower()
    is_rain = main in {"Rain", "Drizzle"} or 300 <= weather_code <= 531 or rain_probability >= 40
    is_cloudy = main == "Clouds" or "cloud" in condition.lower()
    is_poor_visibility = main in {"Mist", "Smoke", "Haze", "Dust", "Fog", "Sand", "Ash"} or (
        visibility is not None and float(visibility) < 3000
    )

    weather_type = "Sunny"
    risk_level = "Low Risk"
    probability = max(5, min(100, rain_probability))
    message = f"Walking conditions look generally safe {adverb}. Stay aware of nearby SafeWalk reports."

    if is_thunderstorm:
        weather_type = "Thunderstorm"
        risk_level = "Critical Risk" if rain_probability >= 80 or wind >= 40 else "High Risk"
        probability = max(probability, 90 if risk_level == "Critical Risk" else 82)
        message = f"Thunderstorm risk is expected {adverb}. Delay walking and avoid open areas, trees, and flooded paths."
    elif temp >= 38:
        weather_type = "Extreme Heat"
        risk_level = "Critical Risk"
        probability = max(probability, 90)
        message = f"Extreme heat is expected {adverb}. Avoid long walks and stay hydrated."
    elif temp >= 36:
        weather_type = "Extreme Heat"
        risk_level = "High Risk"
        probability = max(probability, 78)
        message = f"Extreme heat is likely {adverb}. Use shaded routes, bring water, and shorten outdoor walking."
    elif is_rain and rain_probability >= 70:
        weather_type = "Rainy"
        risk_level = "High Risk"
        probability = max(probability, rain_probability)
        message = f"Rain is likely {adverb}. Bring umbrella and use safer main roads."
    elif is_rain:
        weather_type = "Rainy"
        risk_level = "Moderate Risk"
        probability = max(probability, rain_probability)
        message = f"Rain may affect walking {adverb}. Bring umbrella and avoid slippery shortcuts."
    elif wind >= 40:
        weather_type = "Strong Wind"
        risk_level = "High Risk"
        probability = max(probability, 75)
        message = f"Strong wind is expected {adverb}. Avoid exposed roads and unstable structures."
    elif wind >= 25:
        weather_type = "Strong Wind"
        risk_level = "Moderate Risk"
        probability = max(probability, 55)
        message = f"Wind may affect walking {adverb}. Use sheltered, visible routes."
    elif is_poor_visibility:
        weather_type = "Poor Visibility"
        risk_level = "Moderate Risk"
        probability = max(probability, 58)
        message = f"Visibility may be poor {adverb}. Use well-lit main roads and stay visible."
    elif temp >= 33:
        weather_type = "Sunny"
        risk_level = "Heat Caution"
        probability = max(probability, 50)
        message = f"Sunny and hot conditions are expected {adverb}. Bring water and rest in shaded areas."
    elif is_cloudy:
        weather_type = "Cloudy"
        risk_level = "Moderate Risk" if rain_probability >= 30 or is_poor_visibility else "Low Risk"
        probability = max(probability, 35 if risk_level == "Low Risk" else 48)
        message = f"Cloudy conditions are expected {adverb}. Check rain changes before walking."

    if rain_probability >= 80:
        weather_type = "Flood Risk" if weather_type != "Thunderstorm" else weather_type
        risk_level = "High Risk" if risk_level != "Critical Risk" else risk_level
        message = f"Heavy rain may cause flood-prone walking paths {adverb}. Avoid low-lying shortcuts."

    return {
        "weather_type": weather_type,
        "risk_level": risk_level,
        "probability": int(min(100, probability)),
        "title": period_config["title"],
        "message": message,
    }


def build_period_weather_cards(weather_data):
    current = weather_data.get("current", {})
    hourly = weather_data.get("hourly", [])
    today = weather_data.get("weather_today", current)
    cards = []
    period_points = {
        "morning": [point for point in hourly if _hour_in_range(point.get("label"), 5, 10)],
        "afternoon": [point for point in hourly if _hour_in_range(point.get("label"), 11, 17)],
        "evening": [point for point in hourly if _hour_in_range(point.get("label"), 18, 22)],
    }
    for period, config in PERIODS.items():
        point_data = _summarize_points(period_points[period], current)
        period_weather = {**current, **point_data}
        alert = calculate_weather_alert({"current": period_weather}, period)
        cards.append(
            {
                "period": period,
                "label": config["label"],
                "date": today.get("date", current.get("date", "")),
                "condition": alert["weather_type"],
                "temperature": point_data["temp"],
                "rain_probability": point_data["precipitation"],
                "walking_safety_index": alert["risk_level"],
                "index_probability": alert["probability"],
                "advice": alert["message"],
                "index_key": _risk_key(alert["risk_level"]),
            }
        )
    return cards


def _summarize_points(points, fallback):
    if not points:
        return {
            "temp": fallback.get("temp", fallback.get("temperature", 0)),
            "precipitation": fallback.get("precipitation", fallback.get("rain_probability", 0)),
            "wind": fallback.get("wind", fallback.get("wind_speed", 0)),
            "humidity": fallback.get("humidity", 0),
        }
    return {
        "temp": round(sum(point.get("temperature", 0) for point in points) / len(points)),
        "precipitation": max(point.get("precipitation", 0) for point in points),
        "wind": max(point.get("wind", 0) for point in points),
        "humidity": round(sum(point.get("humidity", 0) for point in points) / len(points)),
    }


def _hour_in_range(label, start, end):
    try:
        hour_text, suffix = str(label).split()
        hour = int(hour_text)
        if suffix.upper() == "PM" and hour != 12:
            hour += 12
        if suffix.upper() == "AM" and hour == 12:
            hour = 0
        return start <= hour <= end
    except (ValueError, AttributeError):
        return False


def _risk_key(risk_level):
    value = risk_level.lower()
    if "critical" in value:
        return "critical"
    if "high" in value or "heat" in value:
        return "high"
    if "moderate" in value:
        return "moderate"
    if "low" in value:
        return "low"
    return "safe"
