from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialApp

class Command(BaseCommand):
    help = 'Deletes duplicate Google SocialApp records from the database.'

    def handle(self, *args, **options):
        # Delete all SocialApp objects where provider="google"
        # Since we use SOCIALACCOUNT_PROVIDERS['google']['APP'] in settings.py,
        # allauth will automatically use that configuration.
        deleted_count, _ = SocialApp.objects.filter(provider='google').delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {deleted_count} duplicate Google SocialApp records.')
        )
        self.stdout.write(
            self.style.NOTICE('allauth will now use the Google configuration from settings.py.')
        )
