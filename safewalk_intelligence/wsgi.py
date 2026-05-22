import os
from pathlib import Path
from shutil import copyfile

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

    database_path = Path(database["NAME"])
    template_path = Path(getattr(settings, "VERCEL_SQLITE_TEMPLATE", ""))
    if template_path.exists() and not database_path.exists():
        database_path.parent.mkdir(parents=True, exist_ok=True)
        copyfile(template_path, database_path)

    from django.core.management import call_command
    from django.db import DatabaseError, connection

    def has_table(table_name):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = %s", [table_name])
                return cursor.fetchone() is not None
        except DatabaseError:
            connection.close()
            return False

    try:
        if not has_table("django_migrations"):
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
