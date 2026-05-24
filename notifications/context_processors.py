from django.conf import settings

from .models import Notification


def notification_center(request):
    if not request.user.is_authenticated:
        return {"VAPID_PUBLIC_KEY": settings.VAPID_PUBLIC_KEY}
    unread = Notification.objects.filter(user=request.user, is_read=False)
    return {
        "VAPID_PUBLIC_KEY": settings.VAPID_PUBLIC_KEY,
        "notification_unread_count": unread.count(),
        "notification_recent": Notification.objects.filter(user=request.user)[:5],
    }
