import logging

from django.core.management import call_command
from django.db import DatabaseError, OperationalError, ProgrammingError

from .models import SafetyReport


logger = logging.getLogger(__name__)


def ensure_sample_reports():
    try:
        if SafetyReport.objects.exists():
            return
        call_command("seed_data", verbosity=0)
    except (DatabaseError, OperationalError, ProgrammingError):
        logger.exception("Could not seed sample reports because the database is not ready")
    except Exception:
        logger.exception("Could not seed sample reports")
