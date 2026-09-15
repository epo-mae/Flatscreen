"""Prepare disposable browser-review data. Never run against the household database."""
import os
from pathlib import Path
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()
from django.conf import settings
from django.core.management import call_command
from household.models import Household, Member
from shopping.models import ShoppingItem
from planning.models import CalendarEvent, DinnerPlan, HouseNotice
from datetime import timedelta
from django.utils import timezone
from zoneinfo import ZoneInfo

if Path(settings.DATA_DIR).resolve() != (settings.BASE_DIR / 'data' / 'review').resolve():
    raise RuntimeError('Set FLATSCREEN_DATA_DIR to this project’s data/review directory.')
call_command('migrate', verbosity=0)
house = Household.current()
house.name = 'The Green House (test)'
house.save()
admin, _ = Member.objects.get_or_create(username='review', defaults={'display_name':'Alex', 'role':'admin'})
admin.set_password('Local-review-only-48219')
admin.save()
Member.objects.get_or_create(username='sam', defaults={'display_name':'Sam'})
for name, quantity, note in [('Olive oil', 1, 'Extra virgin'), ('Coffee beans', 2, 'For the morning ritual'), ('Dishwasher tablets', 1, '')]:
    ShoppingItem.objects.get_or_create(name=name, defaults={'normalized_name':name.casefold(), 'quantity':quantity, 'note':note, 'added_by':admin})
today = timezone.now().astimezone(ZoneInfo(house.timezone)).date()
DinnerPlan.objects.update_or_create(date=today, defaults={'cook':admin, 'meal':'Miso aubergine bowls', 'serving_time':'19:00', 'created_by':admin, 'updated_by':admin})
CalendarEvent.objects.get_or_create(title='Flat inspection', event_date=today + timedelta(days=3), defaults={'category':'maintenance', 'creator':admin})
CalendarEvent.objects.get_or_create(title='House meeting', event_date=today + timedelta(days=1), defaults={'start_time':'18:30', 'creator':admin})
HouseNotice.objects.get_or_create(title='Water off Wednesday', defaults={'message':'The plumber will be here from 10 until 12.', 'importance':'important', 'creator':admin, 'expires_at':timezone.now()+timedelta(days=2)})
print('Disposable review household prepared.')
