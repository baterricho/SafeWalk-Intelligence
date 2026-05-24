import json
import logging
import math

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
try:
    from pywebpush import WebPushException, webpush
except ImportError:  # pragma: no cover - dependency is installed from requirements in deployed environments.
    WebPushException = Exception
    webpush = None

from routes.models import SavedRoute

from .models import Notification, NotificationPreference, PushSubscription

logger = logging.getLogger(__name__)


def get_notification_preference(user):
    preference, _ = NotificationPreference.objects.get_or_create(user=user)
    return preference


def create_in_app_notification(user, title, body, notification_type, url="/dashboard/"):
    if not user or not user.is_authenticated:
        return None
    return Notification.objects.create(
        user=user,
        title=title[:160],
        body=body[:1000],
        notification_type=notification_type[:80],
        url=url or "/dashboard/",
    )


def send_push_notification(user, title, body, url="/dashboard/", tag=None, notification_type="general"):
    create_in_app_notification(user, title, body, notification_type, url)
    subscriptions = PushSubscription.objects.filter(user=user, is_active=True)
    if not subscriptions.exists():
        return 0

    vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", "")
    vapid_public_key = getattr(settings, "VAPID_PUBLIC_KEY", "")
    vapid_admin_email = getattr(settings, "VAPID_ADMIN_EMAIL", "")
    if not webpush:
        logger.warning("pywebpush is not installed; stored in-app notification only.")
        return 0
    if not (vapid_private_key and vapid_public_key and vapid_admin_email):
        logger.warning("VAPID keys are not configured; stored in-app notification only.")
        return 0

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "url": url or "/dashboard/",
            "tag": tag or notification_type,
        }
    )
    sent = 0
    for subscription in subscriptions:
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": f"mailto:{vapid_admin_email}"},
            )
            sent += 1
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in {404, 410}:
                subscription.is_active = False
                subscription.save(update_fields=["is_active", "updated_at"])
            logger.warning("Push notification failed for subscription %s: %s", subscription.pk, exc)
        except Exception:
            logger.exception("Unexpected push notification failure for subscription %s", subscription.pk)
    return sent


def send_push_to_users(users, title, body, url="/dashboard/", notification_type="general"):
    sent = 0
    for user in users:
        sent += send_push_notification(user, title, body, url=url, notification_type=notification_type)
    return sent


def notify_new_report(report):
    if report.risk_level not in {"critical", "high"}:
        return 0

    reporter_id = report.user_id
    recipients = nearby_report_users(report)
    title = "New Safety Report Nearby"
    body = f"A {report.get_risk_level_display()} report was posted near {report.location_name}: {report.title}."
    url = reverse("report_detail", args=[report.pk])
    sent = 0
    for user in recipients:
        if user.id == reporter_id:
            continue
        preference = get_notification_preference(user)
        if not preference.nearby_reports_enabled:
            continue
        if preference.critical_only and report.risk_level != "critical":
            continue
        sent += send_push_notification(user, title, body, url=url, notification_type="nearby_report")
    return sent


def notify_report_comment(report, actor, comment):
    recipients = set()
    if report.user and report.user_id != actor.id:
        recipients.add(report.user)
    commenters = get_user_model().objects.filter(
        report_confirmations__report=report,
        report_confirmations__comment__gt="",
    ).exclude(id=actor.id)
    recipients.update(commenters)

    snippet = (comment or "shared a community update.").strip()
    if len(snippet) > 100:
        snippet = f"{snippet[:97]}..."
    title = "New Comment on Your Report" if report.user_id and report.user_id != actor.id else "New Comment on a Report"
    body = f"{actor.username} commented: \"{snippet}\""
    url = reverse("report_detail", args=[report.pk])

    sent = 0
    for user in recipients:
        preference = get_notification_preference(user)
        if preference.comments_enabled:
            sent += send_push_notification(user, title, body, url=url, notification_type="report_comment")
    return sent


def notify_report_update(report, actor, update_text):
    recipients = set()
    if report.user and (not actor or report.user_id != actor.id):
        recipients.add(report.user)
    commenters = get_user_model().objects.filter(
        report_confirmations__report=report,
        report_confirmations__comment__gt="",
    )
    if actor:
        commenters = commenters.exclude(id=actor.id)
    recipients.update(commenters)

    title = "Report Update"
    body = f"{report.title}: {update_text}"[:1000]
    url = reverse("report_detail", args=[report.pk])
    sent = 0
    for user in recipients:
        preference = get_notification_preference(user)
        if preference.comments_enabled:
            sent += send_push_notification(user, title, body, url=url, notification_type="report_update")
    return sent


def nearby_report_users(report, radius_km=2.0):
    users_by_id = {}
    report_lat = float(report.latitude)
    report_lon = float(report.longitude)
    routes = SavedRoute.objects.select_related("user").filter(user__push_subscriptions__is_active=True).distinct()
    for route in routes:
        route_points = [
            (route.start_latitude, route.start_longitude),
            (route.end_latitude, route.end_longitude),
        ]
        if route.route_geometry and isinstance(route.route_geometry, dict):
            route_points.extend(_geometry_points(route.route_geometry))
        for lat, lon in route_points:
            if lat is None or lon is None:
                continue
            if _distance_km(report_lat, report_lon, float(lat), float(lon)) <= radius_km:
                users_by_id[route.user_id] = route.user
                break
    return list(users_by_id.values())


def _geometry_points(geometry):
    coordinates = geometry.get("coordinates") or []
    if geometry.get("type") == "LineString":
        return [(lat, lon) for lon, lat in coordinates[:50]]
    if geometry.get("type") == "Feature":
        return _geometry_points(geometry.get("geometry") or {})
    return []


def _distance_km(lat1, lon1, lat2, lon2):
    radius = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
