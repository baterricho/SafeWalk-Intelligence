import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "safewalk_intelligence.settings")

application = get_wsgi_application()


def bootstrap_vercel_sqlite():
    from django.conf import settings

    if not getattr(settings, "VERCEL_AUTO_MIGRATE", False):
        return

    database = settings.DATABASES["default"]
    if database.get("ENGINE") != "django.db.backends.sqlite3":
        return

    from django.core.management import call_command
    from django.db import DatabaseError, connection

    try:
        call_command("migrate", interactive=False, verbosity=0)
        if getattr(settings, "VERCEL_SEED_DATA", False):
            from reports.models import SafetyReport

            if not SafetyReport.objects.exists():
                call_command("seed_data", verbosity=0)
    except DatabaseError:
        connection.close()
        raise


bootstrap_vercel_sqlite()
app = application
