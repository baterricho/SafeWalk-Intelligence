from django.core.management.base import BaseCommand

from notifications.views import send_weather_notifications_for_current_period


class Command(BaseCommand):
    help = "Send SafeWalk weather push notifications for the current Manila time period."

    def handle(self, *args, **options):
        result = send_weather_notifications_for_current_period()
        self.stdout.write(self.style.SUCCESS(f"Weather notifications: {result}"))
