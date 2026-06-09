import logging
import os
from pathlib import Path
from shutil import copyfile

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "safewalk_intelligence.settings")
logger = logging.getLogger(__name__)

application = get_wsgi_application()


def bootstrap_vercel():
    from django.conf import settings

    # 1. Handle SQLite if template exists
    database = settings.DATABASES["default"]
    if database.get("ENGINE") == "django.db.backends.sqlite3":
        database_path = Path(database["NAME"])
        template_path = Path(getattr(settings, "VERCEL_SQLITE_TEMPLATE", ""))
        if template_path.exists() and not database_path.exists():
            database_path.parent.mkdir(parents=True, exist_ok=True)
            copyfile(template_path, database_path)

    # 2. Run Migrations and Site Fix
    if not getattr(settings, "VERCEL_AUTO_MIGRATE", False):
        return

    from django.core.management import call_command
    from django.db import DatabaseError, connection

    try:
        # Check if tables exist by trying to query Site model (common allauth dependency)
        # or just run migrate --no-input which is safe.
        call_command("migrate", interactive=False, verbosity=1)
        
        # Ensure Site object is correct for production domain
        call_command("fix_site", verbosity=1)
        
        # Remove duplicate Google SocialApps to prevent MultipleObjectsReturned error
        call_command("fix_google_oauth", verbosity=1)

        if getattr(settings, "VERCEL_SEED_DATA", False):
            from reports.models import SafetyReport
            if not SafetyReport.objects.exists():
                call_command("seed_data", verbosity=1)
    except Exception:
        logger.exception("Vercel bootstrap failed")
        # We don't necessarily want to crash the whole app if seeding fails,
        # but migrations are usually critical.


if os.environ.get("VERCEL"):
    bootstrap_vercel()
app = application
