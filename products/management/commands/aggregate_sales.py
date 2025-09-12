from django.core.management.base import BaseCommand
from django.conf import settings
from products.models import Sales

class Command(BaseCommand):
    
    help = 'Aggregate sales data for the current year from many to many bridge tables -> Sales table'

    def handle(self, *args, **options):
        year = settings.CURRENT_ORDER_YEAR
        self.stdout.write(f"📅 Current order year (from settings): {year}")

       