from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Check if Google OAuth Client ID and Secret are loaded."

    def handle(self, *args, **options):
        google = settings.SOCIALACCOUNT_PROVIDERS.get("google", {})
        app = google.get("APP", {})

        client_id = app.get("client_id")
        secret = app.get("secret")

        if client_id:
            self.stdout.write(self.style.SUCCESS(f"GOOGLE_CLIENT_ID loaded: {client_id[:18]}..."))
        else:
            self.stdout.write(self.style.ERROR("GOOGLE_CLIENT_ID is missing or empty."))

        if secret:
            self.stdout.write(self.style.SUCCESS("GOOGLE_CLIENT_SECRET loaded."))
        else:
            self.stdout.write(self.style.ERROR("GOOGLE_CLIENT_SECRET is missing or empty."))

        if client_id and not client_id.endswith(".apps.googleusercontent.com"):
            self.stdout.write(self.style.WARNING("GOOGLE_CLIENT_ID does not look like a valid Google OAuth Client ID."))
