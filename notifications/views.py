import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from dashboard.weather_service import get_weather_data
from routes.models import SavedRoute

from .models import Notification, NotificationLog, NotificationPreference, PushSubscription
from .services import get_notification_preference, send_push_notification
from .weather import calculate_weather_alert, current_weather_period


@login_required
@require_POST
def subscribe(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
        endpoint = payload["endpoint"]
        keys = payload["keys"]
        p256dh = keys["p256dh"]
        auth = keys["auth"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid push subscription payload."}, status=400)

    subscription, _ = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
            "is_active": True,
        },
    )
    get_notification_preference(request.user)
    return JsonResponse({"ok": True, "subscription_id": subscription.pk, "enabled": True})


@login_required
@require_POST
def unsubscribe(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}
    endpoint = payload.get("endpoint")
    subscriptions = PushSubscription.objects.filter(user=request.user, is_active=True)
    if endpoint:
        subscriptions = subscriptions.filter(endpoint=endpoint)
    updated = subscriptions.update(is_active=False, updated_at=timezone.now())
    return JsonResponse({"ok": True, "updated": updated, "enabled": False})


@login_required
@require_GET
def status(request):
    return JsonResponse(
        {
            "enabled": PushSubscription.objects.filter(user=request.user, is_active=True).exists(),
            "publicKey": settings.VAPID_PUBLIC_KEY,
            "permission": "default",
        }
    )


@login_required
def settings_page(request):
    preference = get_notification_preference(request.user)
    if request.method == "POST":
        for field in [
            "weather_enabled",
            "morning_weather",
            "afternoon_weather",
            "evening_weather",
            "nearby_reports_enabled",
            "comments_enabled",
            "critical_only",
        ]:
            setattr(preference, field, request.POST.get(field) == "on")
        preference.save()
        messages.success(request, "Notification preferences saved.")
        return redirect("notification_settings")
    return render(request, "notifications/settings.html", {"preference": preference})


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)[:100]
    return render(request, "notifications/list.html", {"notifications": notifications})


@login_required
@require_POST
def mark_read(request):
    notification_id = request.POST.get("notification_id")
    queryset = Notification.objects.filter(user=request.user, is_read=False)
    if notification_id:
        queryset = queryset.filter(pk=notification_id)
    updated = queryset.update(is_read=True)
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        return redirect("notification_list")
    return JsonResponse({"ok": True, "updated": updated})


@csrf_exempt
@require_GET
def weather_notifications_cron(request):
    expected = getattr(settings, "CRON_SECRET", "")
    auth_header = request.headers.get("authorization", "")
    token = request.GET.get("secret", "")
    if expected and auth_header != f"Bearer {expected}" and token != expected:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    result = send_weather_notifications_for_current_period()
    return JsonResponse(result)


def send_weather_notifications_for_current_period():
    period = current_weather_period()
    users = (
        get_user_model()
        .objects.filter(push_subscriptions__is_active=True)
        .distinct()
    )
    today = timezone.localdate()
    sent = 0
    skipped = 0
    for user in users:
        preference, _ = NotificationPreference.objects.get_or_create(user=user)
        if not preference.weather_enabled or not getattr(preference, f"{period}_weather", True):
            skipped += 1
            continue
        if NotificationLog.objects.filter(
            user=user,
            notification_type="weather",
            period=period,
            sent_at__date=today,
        ).exists():
            skipped += 1
            continue
        weather_data = _weather_for_user(user)
        alert = calculate_weather_alert(weather_data, period)
        if preference.critical_only and "Critical" not in alert["risk_level"] and "High" not in alert["risk_level"]:
            skipped += 1
            continue
        body = f"{alert['message']} Walking Risk: {alert['risk_level']}."
        send_push_notification(
            user,
            alert["title"],
            body,
            url="/dashboard/#weather",
            tag=f"weather-{period}-{today.isoformat()}",
            notification_type="weather",
        )
        NotificationLog.objects.create(
            user=user,
            notification_type="weather",
            period=period,
            title=alert["title"],
            body=body,
            metadata={"weather_type": alert["weather_type"], "risk_level": alert["risk_level"], "probability": alert["probability"]},
        )
        sent += 1
    return {"ok": True, "period": period, "sent": sent, "skipped": skipped}


def _weather_for_user(user):
    route = (
        SavedRoute.objects.filter(user=user)
        .exclude(start_latitude__isnull=True)
        .exclude(start_longitude__isnull=True)
        .order_by("-updated_at")
        .first()
    )
    if route:
        return get_weather_data(
            lat=float(route.start_latitude),
            lon=float(route.start_longitude),
            location_name=route.start_location,
        )
    return get_weather_data()
