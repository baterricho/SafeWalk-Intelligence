from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = "Update the Site object for the production domain."

    def handle(self, *args, **options):
        # Site.objects.update_or_create can be risky if multiple exist, 
        # but for SITE_ID=1 it's usually what we want.
        site, created = Site.objects.update_or_create(
            id=1,
            defaults={
                "domain": "safe-walk-intelligence.vercel.app",
                "name": "SafeWalk Intelligence",
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created site: {site.domain}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated site: {site.domain}"))
