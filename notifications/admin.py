from django.contrib import admin

from .models import Notification, NotificationLog, NotificationPreference, PushSubscription


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("user__username", "user__email", "endpoint", "user_agent")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "weather_enabled", "nearby_reports_enabled", "comments_enabled", "critical_only")
    search_fields = ("user__username", "user__email")


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("user", "notification_type", "period", "title", "sent_at")
    list_filter = ("notification_type", "period", "sent_at")
    search_fields = ("user__username", "title", "body")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "notification_type", "is_read", "created_at")
    list_filter = ("notification_type", "is_read", "created_at")
    search_fields = ("user__username", "title", "body")
