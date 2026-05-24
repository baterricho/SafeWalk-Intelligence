from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=700, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user} push subscription"


class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preference")
    weather_enabled = models.BooleanField(default=True)
    morning_weather = models.BooleanField(default=True)
    afternoon_weather = models.BooleanField(default=True)
    evening_weather = models.BooleanField(default=True)
    nearby_reports_enabled = models.BooleanField(default=True)
    comments_enabled = models.BooleanField(default=True)
    critical_only = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} notification preferences"


class NotificationLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_logs")
    notification_type = models.CharField(max_length=80)
    period = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=160)
    body = models.TextField(max_length=1000)
    sent_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["user", "notification_type", "period", "sent_at"]),
        ]

    def __str__(self):
        return f"{self.notification_type} for {self.user}"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=160)
    body = models.TextField(max_length=1000)
    notification_type = models.CharField(max_length=80)
    url = models.CharField(max_length=500, default="/dashboard/")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
        ]

    def __str__(self):
        return self.title
