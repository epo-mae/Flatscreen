import hashlib
import json
import uuid
from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from household.models import Household, Member, DisplayDevice, ActivityEntry, WeatherSnapshot
from household.weather import _alerts, get_weather
from shopping.models import ShoppingItem
from presence.models import PresenceEvent
from planning.models import CalendarEvent, Chore, ChoreCompletion, DinnerPlan, HouseNotice
from planning.views import upcoming_occurrences


class FoundationTests(TestCase):
    def setUp(self):
        weather = {'available': True, 'location': 'Auckland', 'temperature': 17, 'feels_like': 16,
                   'high': 20, 'low': 12, 'uv': 5.2, 'description': 'Partly cloudy', 'alerts': [],
                   'updated_at': '2026-09-15T00:00:00+00:00', 'stale': False}
        self.weather_patcher = patch('shopping.views.get_weather', return_value=weather)
        self.weather_patcher.start(); self.addCleanup(self.weather_patcher.stop)
        self.house = Household.current()
        self.admin = Member.objects.create_user(username='admin', display_name='Alex', password='Household-test-4821', role='admin')
        self.member = Member.objects.create_user(username='member', display_name='Sam', password='Household-test-5932')
        self.sign_in(self.client, self.member)

    def sign_in(self, client, member):
        client.force_login(member)
        session = client.session
        session['access_version'] = member.access_version
        session.save()

    def mutation(self, payload, client=None):
        payload.setdefault('operation_id', str(uuid.uuid4()))
        return (client or self.client).post('/api/shopping/', data=json.dumps(payload), content_type='application/json')

    def add(self, name='Milk', **kwargs):
        response = self.mutation({'action':'add', 'name':name, **kwargs})
        self.assertEqual(response.status_code, 200, response.content)
        return ShoppingItem.objects.get(pk=response.json()['item_id'])

    def display_client(self):
        device = DisplayDevice.objects.create(approved=True, expires_at=timezone.now() + timedelta(minutes=10))
        client = Client()
        session = client.session
        session['display_id'] = device.pk
        session.save()
        return client, device

    def test_unauthenticated_access_blocked(self):
        c = Client()
        self.assertEqual(c.get('/api/state/').status_code, 401)
        self.assertEqual(self.mutation({'action':'add', 'name':'Milk'}, c).status_code, 401)
        self.assertEqual(c.get('/').status_code, 302)

    def test_member_cannot_administer(self):
        self.assertEqual(self.client.get('/settings/').status_code, 403)
        self.assertEqual(self.client.post('/settings/', {'action':'household', 'name':'Changed', 'timezone':'UTC'}).status_code, 403)

    def test_saved_item_visible_to_second_client_and_display(self):
        self.add(note='Private note')
        c = Client(); self.sign_in(c, self.admin)
        self.assertEqual(c.get('/api/state/').json()['items'][0]['name'], 'Milk')
        display, _ = self.display_client()
        row = display.get('/api/state/?view=display').json()['items'][0]
        self.assertNotIn('note', row)
        self.assertNotIn('added_by', row)
        self.assertEqual(self.mutation({'action':'clear_all', 'confirmed':True}, display).status_code, 401)
        self.assertEqual(display.get('/api/state/').status_code, 401)

    def test_display_receives_only_safe_member_presence(self):
        PresenceEvent.objects.create(member=self.member, status='HOME', changed_by=self.member)
        display, _ = self.display_client()
        members = display.get('/api/state/?view=display').json()['members']
        sam = next(member for member in members if member['name'] == 'Sam')
        self.assertEqual(sam['presence'], 'HOME')
        self.assertNotIn('username', sam)
        self.assertNotIn('is_self', sam)

    def test_member_can_set_only_their_own_presence(self):
        response = self.client.post('/api/presence/', data=json.dumps({
            'operation_id':str(uuid.uuid4()), 'status':'HOME', 'member_id':self.admin.pk,
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        event = PresenceEvent.objects.get()
        self.assertEqual(event.member, self.member)
        self.assertEqual(event.changed_by, self.member)
        self.assertEqual(event.source, 'manual')

    def test_presence_retry_is_idempotent_and_same_state_is_not_logged_twice(self):
        operation_id = str(uuid.uuid4())
        payload = {'operation_id':operation_id, 'status':'OUT'}
        first = self.client.post('/api/presence/', data=json.dumps(payload), content_type='application/json')
        second = self.client.post('/api/presence/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(first.json(), second.json())
        same = self.client.post('/api/presence/', data=json.dumps({
            'operation_id':str(uuid.uuid4()), 'status':'OUT',
        }), content_type='application/json')
        self.assertFalse(same.json()['changed'])
        self.assertEqual(PresenceEvent.objects.count(), 1)

    def test_presence_requires_authentication_and_valid_state(self):
        payload = {'operation_id':str(uuid.uuid4()), 'status':'MAYBE'}
        self.assertEqual(Client().post('/api/presence/', data=json.dumps(payload), content_type='application/json').status_code, 401)
        self.assertEqual(self.client.post('/api/presence/', data=json.dumps(payload), content_type='application/json').status_code, 400)

    def test_conditional_refresh_and_revision(self):
        response = self.client.get('/api/state/')
        old_etag = response['ETag']
        self.assertEqual(self.client.get('/api/state/', HTTP_IF_NONE_MATCH=old_etag).status_code, 304)
        self.add()
        self.assertEqual(self.client.get('/api/state/', HTTP_IF_NONE_MATCH=old_etag).status_code, 200)

    def test_retry_is_idempotent(self):
        payload = {'action':'add', 'name':'Milk', 'operation_id':str(uuid.uuid4())}
        first = self.mutation(payload)
        second = self.mutation(payload)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(ShoppingItem.objects.count(), 1)
        self.assertEqual(ActivityEntry.objects.count(), 1)
        payload['name'] = 'Bread'
        self.assertEqual(self.mutation(payload).status_code, 409)

    def test_stale_edit_does_not_overwrite(self):
        item = self.add()
        self.assertEqual(self.mutation({'action':'quantity', 'id':item.pk, 'version':1, 'delta':1}).status_code, 200)
        self.assertEqual(self.mutation({'action':'edit', 'id':item.pk, 'version':1, 'name':'Bread'}).status_code, 409)
        item.refresh_from_db()
        self.assertEqual((item.name, item.quantity), ('Milk', 2))

    def test_duplicate_requires_choice_and_merges_quantity(self):
        self.add()
        payload = {'action':'add', 'name':' milk ', 'quantity':2}
        self.assertTrue(self.mutation(payload).json()['duplicate'])
        payload.update(duplicate='merge', operation_id=str(uuid.uuid4()))
        self.assertEqual(self.mutation(payload).status_code, 200)
        self.assertEqual(ShoppingItem.objects.get().quantity, 3)

    def test_purchase_and_reopen_attribution(self):
        item = self.add()
        self.mutation({'action':'purchase', 'id':item.pk, 'version':1, 'purchased':True})
        item.refresh_from_db()
        self.assertEqual(item.purchased_by, self.member)
        self.assertIsNotNone(item.purchased_at)
        self.mutation({'action':'purchase', 'id':item.pk, 'version':2, 'purchased':False})
        item.refresh_from_db()
        self.assertIsNone(item.purchased_by)
        self.assertIsNone(item.purchased_at)

    def test_clear_requires_confirmation_and_current_revision(self):
        self.add()
        self.assertEqual(self.mutation({'action':'clear_all'}).status_code, 400)
        self.assertEqual(self.mutation({'action':'clear_all', 'confirmed':True, 'revision':1}).status_code, 409)
        revision = self.client.get('/api/state/').json()['revision']
        self.assertEqual(self.mutation({'action':'clear_all', 'confirmed':True, 'revision':revision}).status_code, 200)
        self.assertEqual(self.client.get('/api/state/').json()['items'], [])
        self.assertIsNotNone(ShoppingItem.objects.get().deleted_at)

    def test_remove_and_undo(self):
        item = self.add()
        undo = self.mutation({'action':'delete', 'id':item.pk, 'version':1}).json()['undo']
        self.assertEqual(self.mutation({'action':'restore', **undo}).status_code, 200)
        self.assertEqual(len(self.client.get('/api/state/').json()['items']), 1)

    def test_revocation_checked_even_with_old_etag(self):
        display, device = self.display_client()
        etag = display.get('/api/state/?view=display')['ETag']
        device.revoked = True; device.save()
        self.assertEqual(display.get('/api/state/?view=display', HTTP_IF_NONE_MATCH=etag).status_code, 403)

    def test_deactivate_then_reactivate_does_not_restore_old_session(self):
        admin_client = Client(); self.sign_in(admin_client, self.admin)
        payload = {'action':'toggle_member', 'member_id':self.member.pk}
        admin_client.post('/settings/', payload)
        admin_client.post('/settings/', payload)
        self.assertEqual(self.client.get('/api/state/').status_code, 401)

    def test_display_pairing_requires_admin(self):
        screen = Client()
        self.assertEqual(screen.post('/display/pair/').status_code, 302)
        code = screen.session['pair_code']
        self.assertEqual(self.client.post('/settings/', {'action':'pair', 'code':code}).status_code, 403)
        self.sign_in(self.client, self.admin)
        self.client.post('/settings/', {'action':'pair', 'code':code})
        self.assertEqual(screen.get('/api/state/?view=display').status_code, 200)
        self.assertIsNone(DisplayDevice.objects.get().pairing_hash)

    def test_expired_pair_code_rejected(self):
        DisplayDevice.objects.create(pairing_hash=hashlib.sha256(b'12345678').hexdigest(), expires_at=timezone.now()-timedelta(seconds=1))
        self.sign_in(self.client, self.admin)
        self.client.post('/settings/', {'action':'pair', 'code':'12345678'})
        self.assertFalse(DisplayDevice.objects.get().approved)

    def test_mutation_requires_csrf(self):
        c = Client(enforce_csrf_checks=True); self.sign_in(c, self.member)
        self.assertEqual(self.mutation({'action':'add', 'name':'Milk'}, c).status_code, 403)

    def test_bad_input_does_not_write(self):
        for quantity in (0, -1, 1000, True, 'two'):
            self.assertEqual(self.mutation({'action':'add', 'name':'Milk', 'quantity':quantity}).status_code, 400)
        self.assertEqual(ShoppingItem.objects.count(), 0)

    def test_templates_render(self):
        self.assertContains(self.client.get('/'), 'The shopping list')
        self.sign_in(self.client, self.admin)
        self.assertContains(self.client.get('/settings/'), 'Pair the household screen')
        display, _ = self.display_client()
        self.assertContains(display.get('/display/'), 'To pick up')
        self.assertContains(display.get('/display/'), 'Who’s home')
        self.assertContains(Client().get('/display/offline/'), 'Connecting to your household')

    def test_display_preview_is_available_to_members(self):
        self.assertContains(self.client.get('/display/preview/'), 'data-mode="preview"')
        self.client.logout()
        self.assertEqual(self.client.get('/display/preview/').status_code, 302)

    def test_display_state_includes_today_weather(self):
        display, _ = self.display_client()
        weather = display.get('/api/state/?view=display').json()['weather']
        self.assertEqual((weather['high'], weather['low'], weather['feels_like'], weather['uv']), (20, 12, 16, 5.2))

    @patch('household.forms.find_location', return_value={
        'name': 'Wellington, Wellington, New Zealand', 'latitude': -41.28664, 'longitude': 174.77557,
    })
    def test_admin_can_change_weather_location(self, find_location):
        self.sign_in(self.client, self.admin)
        response = self.client.post('/settings/', {'action':'weather', 'location':'Wellington'})
        self.assertEqual(response.status_code, 302)
        self.house.refresh_from_db()
        self.assertEqual(self.house.weather_location, 'Wellington, Wellington, New Zealand')
        self.assertTrue(self.house.weather_enabled)
        find_location.assert_called_once_with('Wellington')

    def test_invalid_member_form_stays_open_and_explains_failure(self):
        self.sign_in(self.client, self.admin)
        response = self.client.post('/settings/', {
            'action':'member', 'username':'james', 'display_name':'James',
            'role':'member', 'password1':'short', 'password2':'short',
        })
        self.assertContains(response, '<details open>', html=False)
        self.assertContains(response, 'The member was not created')
        self.assertFalse(Member.objects.filter(username='james').exists())

    def test_member_list_shows_sign_in_username(self):
        self.sign_in(self.client, self.admin)
        self.assertContains(self.client.get('/settings/'), 'Username: member')

    def test_login_labels_username_clearly(self):
        self.client.logout()
        self.assertContains(self.client.get('/login/'), 'Username (not display name)')

    def test_login_rate_limit(self):
        c = Client()
        for _ in range(10):
            c.post('/login/', {'username':'admin', 'password':'wrong'})
        self.assertEqual(c.post('/login/', {'username':'admin', 'password':'wrong'}).status_code, 429)

    def test_successful_login_does_not_consume_failure_limit(self):
        c = Client()
        for _ in range(12):
            response = c.post('/login/', {'username':'member', 'password':'Household-test-5932'})
            self.assertEqual(response.status_code, 302)
            c.post('/logout/')

    def test_login_limits_are_separate_per_username(self):
        c = Client()
        for _ in range(10):
            c.post('/login/', {'username':'unknown', 'password':'wrong'})
        self.assertEqual(c.post('/login/', {'username':'member', 'password':'Household-test-5932'}).status_code, 302)

    @patch('shopping.views.transaction.atomic')
    def test_state_refresh_does_not_open_write_transaction(self, atomic):
        self.assertEqual(self.client.get('/api/state/').status_code, 200)
        atomic.assert_not_called()

    def test_invalid_timezone_rejected(self):
        self.sign_in(self.client, self.admin)
        response = self.client.post('/settings/', {'action':'household', 'name':'Our home', 'timezone':'Unknown/Place'})
        self.assertContains(response, 'Use a valid timezone')
        self.house.refresh_from_db()
        self.assertEqual(self.house.timezone, 'Pacific/Auckland')

    def test_profile_requires_sign_in(self):
        self.client.logout()
        self.assertEqual(self.client.get('/profile/').status_code, 302)

    def test_member_can_change_their_display_name(self):
        self.assertContains(self.client.get('/profile/'), 'Display name')
        response = self.client.post('/profile/', {'action':'display_name', 'display_name':'Samwise'})
        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertEqual(self.member.display_name, 'Samwise')
        self.assertIn('Changed their display name', ActivityEntry.objects.get().message)
        self.assertEqual(self.client.get('/api/state/').status_code, 200)

    def test_member_can_change_their_password_and_stays_signed_in(self):
        response = self.client.post('/profile/', {
            'action':'password', 'old_password':'Household-test-5932',
            'new_password1':'Fresh-home-8310', 'new_password2':'Fresh-home-8310',
        })
        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password('Fresh-home-8310'))
        self.assertEqual(self.client.get('/api/state/').status_code, 200)

    def test_password_change_requires_current_password(self):
        response = self.client.post('/profile/', {
            'action':'password', 'old_password':'wrong-password',
            'new_password1':'Fresh-home-8310', 'new_password2':'Fresh-home-8310',
        })
        self.assertContains(response, 'Your old password was entered incorrectly')
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password('Household-test-5932'))

    def test_shopping_export_requires_sign_in(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/shopping/export/').status_code, 302)

    def test_shopping_export_contains_active_items_only(self):
        self.add(name='Milk')
        second = self.add(name='Olive oil')
        self.mutation({'action':'purchase', 'id':second.pk, 'version':1, 'purchased':True})
        response = self.client.get('/api/shopping/export/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment; filename="shopping-list.csv"', response['Content-Disposition'])
        body = response.content.decode()
        self.assertIn('Quantity,Item,Note', body)
        self.assertIn('1,Milk,', body)
        self.assertNotIn('Olive oil', body)


class SetupTests(TestCase):
    def test_local_setup_and_lockout(self):
        payload = {'name':'Test household', 'timezone':'Pacific/Auckland', 'username':'alex', 'display_name':'Alex', 'role':'admin', 'password1':'Safe-house-test-4921', 'password2':'Safe-house-test-4921'}
        self.assertContains(self.client.get('/setup/'), 'Make yourself')
        self.assertEqual(self.client.post('/setup/', payload).status_code, 302)
        self.assertEqual(Member.objects.get().role, 'admin')
        self.assertEqual(self.client.get('/setup/').status_code, 302)

    def test_remote_setup_blocked(self):
        self.assertEqual(self.client.get('/setup/', REMOTE_ADDR='192.168.1.5').status_code, 403)

    @override_settings(LOCAL_SETUP=False)
    def test_production_setup_disabled(self):
        self.assertEqual(self.client.get('/setup/').status_code, 403)


class WeatherTests(TestCase):
    def setUp(self):
        self.house = Household.current()
        self.house.weather_enabled = True
        self.house.save(update_fields=['weather_enabled'])

    @patch('household.weather._fetch_weather')
    def test_weather_is_cached_and_reused(self, fetch):
        fetch.return_value = {'available': True, 'location': 'Auckland', 'temperature': 18,
            'feels_like': 17, 'high': 21, 'low': 12, 'uv': 7.1,
            'description': 'Clear', 'alerts': ['High UV — sun protection recommended']}
        first = get_weather(self.house)
        second = get_weather(self.house)
        self.assertEqual(second['temperature'], 18)
        self.assertFalse(second['stale'])
        self.assertEqual(fetch.call_count, 1)

    def test_weather_alerts_cover_uv_and_severe_conditions(self):
        alerts = _alerts({'uv_index_max':[9], 'precipitation_probability_max':[90],
            'wind_gusts_10m_max':[30], 'temperature_2m_max':[22],
            'temperature_2m_min':[8], 'weather_code':[95]})
        self.assertEqual(alerts, ['Very high UV — extra sun protection needed', 'Thunderstorms possible'])

    @patch('household.weather._fetch_weather')
    def test_old_weather_is_used_when_refresh_fails(self, fetch):
        from household.weather import WeatherServiceError
        WeatherSnapshot.objects.create(payload={'available':True, 'location':'Auckland', 'temperature':15},
            fetched_at=timezone.now()-timedelta(hours=1))
        fetch.side_effect = WeatherServiceError('offline')
        weather = get_weather(self.house)
        self.assertTrue(weather['stale'])
        self.assertEqual(weather['temperature'], 15)


class PlanningTests(TestCase):
    def setUp(self):
        self.weather_patcher = patch('shopping.views.get_weather', return_value={
            'available': False, 'location': 'Auckland',
        })
        self.weather_patcher.start(); self.addCleanup(self.weather_patcher.stop)
        self.house = Household.current()
        self.member = Member.objects.create_user(username='member', display_name='Sam', password='Household-test-5932')
        self.client.force_login(self.member)
        session = self.client.session
        session['access_version'] = self.member.access_version
        session.save()
        self.today = timezone.now().astimezone(ZoneInfo(self.house.timezone)).date()

    def test_member_can_plan_dinner_and_display_receives_it(self):
        response = self.client.post('/plan/', {
            'action':'dinner', 'dinner-date':self.today.isoformat(), 'dinner-cook':self.member.pk,
            'dinner-meal':'Vegetable curry', 'dinner-serving_time':'19:00', 'dinner-notes':'Use the big pot',
            'dinner-is_happening':'on',
        })
        self.assertEqual(response.status_code, 302)
        state = self.client.get('/api/state/').json()
        dinner = state['dinners'][0]
        self.assertEqual((dinner['cook'], dinner['meal'], dinner['time']), ('Sam', 'Vegetable curry', '19:00'))
        display = self.display_client()
        self.assertEqual(display.get('/api/state/?view=display').json()['dinners'][0]['notes'], '')

    def display_client(self):
        device = DisplayDevice.objects.create(approved=True, expires_at=timezone.now() + timedelta(minutes=10))
        client = Client(); session = client.session; session['display_id'] = device.pk; session.save()
        return client

    def test_notice_expiry_and_importance_filtering(self):
        HouseNotice.objects.create(title='Old', message='Gone', creator=self.member, expires_at=timezone.now()-timedelta(seconds=1))
        HouseNotice.objects.create(title='Normal', message='Hello', creator=self.member)
        HouseNotice.objects.create(title='Water off', message='Wednesday, 10–12', importance='important', creator=self.member)
        notices = self.client.get('/api/state/').json()['notices']
        self.assertEqual([notice['title'] for notice in notices], ['Water off', 'Normal'])
        self.assertNotIn('creator', notices[0])

    def test_member_can_post_expiring_notice(self):
        response = self.client.post('/plan/', {
            'action':'notice', 'notice-title':'Quiet tonight',
            'notice-message':'Early flight tomorrow.', 'notice-importance':'normal',
            'notice-expires_in':'24',
        })
        self.assertEqual(response.status_code, 302)
        notice = HouseNotice.objects.get()
        self.assertEqual(notice.creator, self.member)
        self.assertGreater(notice.expires_at, timezone.now() + timedelta(hours=23))

    def test_member_can_add_chore_and_display_gets_safe_summary(self):
        response = self.client.post('/plan/', {
            'action':'chore', 'chore-title':'Put out recycling', 'chore-assigned_to':self.member.pk,
            'chore-due_date':self.today.isoformat(), 'chore-repeat':'weekly',
            'chore-notes':'Use the blue bin',
        })
        self.assertEqual(response.status_code, 302)
        display = self.display_client()
        chore = display.get('/api/state/?view=display').json()['chores'][0]
        self.assertEqual((chore['title'], chore['assigned_to'], chore['due_label']), ('Put out recycling', 'Sam', 'TODAY'))
        self.assertNotIn('notes', chore)
        self.assertNotIn('id', chore)

    def test_completing_one_time_chore_records_history_and_allows_reopen(self):
        chore = Chore.objects.create(title='Clean fridge', assigned_to=self.member, due_date=self.today,
            creator=self.member)
        self.client.post('/plan/', {'action':'complete_chore', 'record_id':chore.pk, 'expected_due_date':chore.due_date.isoformat()})
        chore.refresh_from_db()
        self.assertIsNotNone(chore.completed_at)
        self.assertEqual(chore.completed_by, self.member)
        self.assertEqual(ChoreCompletion.objects.get().due_date, self.today)
        self.assertEqual(self.client.get('/api/state/').json()['chores'], [])
        self.client.post('/plan/', {'action':'reopen_chore', 'record_id':chore.pk})
        chore.refresh_from_db()
        self.assertIsNone(chore.completed_at)

    def test_completing_repeating_chore_advances_due_date(self):
        chore = Chore.objects.create(title='Bins', assigned_to=self.member,
            due_date=self.today-timedelta(days=15), repeat='weekly', creator=self.member)
        self.client.post('/plan/', {'action':'complete_chore', 'record_id':chore.pk, 'expected_due_date':chore.due_date.isoformat()})
        chore.refresh_from_db()
        self.assertGreater(chore.due_date, self.today)
        self.assertIsNone(chore.completed_at)
        self.assertEqual(ChoreCompletion.objects.count(), 1)

    def test_completing_repeating_chore_early_still_advances_once(self):
        due = self.today + timedelta(days=2)
        chore = Chore.objects.create(title='Water plants', due_date=due, repeat='weekly', creator=self.member)
        self.client.post('/plan/', {'action':'complete_chore', 'record_id':chore.pk, 'expected_due_date':chore.due_date.isoformat()})
        chore.refresh_from_db()
        self.assertEqual(chore.due_date, due + timedelta(days=7))

    def test_stale_repeat_completion_does_not_advance_twice(self):
        chore = Chore.objects.create(title='Bins', due_date=self.today, repeat='weekly', creator=self.member)
        payload = {'action':'complete_chore', 'record_id':chore.pk, 'expected_due_date':self.today.isoformat()}
        self.client.post('/plan/', payload)
        self.client.post('/plan/', payload)
        chore.refresh_from_db()
        self.assertEqual(chore.due_date, self.today + timedelta(days=7))
        self.assertEqual(ChoreCompletion.objects.count(), 1)

    def test_chore_can_be_edited_and_soft_removed(self):
        chore = Chore.objects.create(title='Vacuum', due_date=self.today, creator=self.member)
        response = self.client.post('/plan/', {
            'action':'chore', 'chore_id':chore.pk, 'chore-title':'Vacuum lounge',
            'chore-assigned_to':'', 'chore-due_date':self.today.isoformat(),
            'chore-repeat':'once', 'chore-notes':'',
        })
        self.assertEqual(response.status_code, 302)
        chore.refresh_from_db(); self.assertEqual(chore.title, 'Vacuum lounge')
        self.client.post('/plan/', {'action':'remove_chore', 'record_id':chore.pk})
        chore.refresh_from_db(); self.assertIsNotNone(chore.deleted_at)

    def test_upcoming_events_have_human_countdowns(self):
        CalendarEvent.objects.create(title='Inspection', event_date=self.today+timedelta(days=3), category='maintenance', creator=self.member)
        CalendarEvent.objects.create(title='Past', event_date=self.today-timedelta(days=1), creator=self.member)
        events = self.client.get('/api/state/').json()['events']
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['countdown'], 'IN 3 DAYS')

    def test_member_can_edit_and_soft_remove_event(self):
        event = CalendarEvent.objects.create(title='Meeting', event_date=self.today, creator=self.member)
        response = self.client.post('/plan/', {
            'action':'event', 'event_id':event.pk, 'event-title':'House meeting',
            'event-event_date':self.today.isoformat(), 'event-start_time':'18:00', 'event-end_time':'19:00',
            'event-category':'household', 'event-description':'Kitchen',
        })
        self.assertEqual(response.status_code, 302)
        event.refresh_from_db(); self.assertEqual(event.title, 'House meeting')
        self.client.post('/plan/', {'action':'remove_event', 'record_id':event.pk})
        event.refresh_from_db(); self.assertIsNotNone(event.deleted_at)
        self.assertEqual(self.client.get('/api/state/').json()['events'], [])

    def test_invalid_event_time_is_shown_without_writing(self):
        response = self.client.post('/plan/', {
            'action':'event', 'event-title':'Visit', 'event-event_date':self.today.isoformat(),
            'event-start_time':'20:00', 'event-end_time':'19:00', 'event-category':'visitor',
        })
        self.assertContains(response, 'End time must be later')
        self.assertEqual(CalendarEvent.objects.count(), 0)

    def test_planner_requires_sign_in(self):
        page = self.client.get('/plan/')
        self.assertContains(page, 'id_event-title')
        self.assertContains(page, 'id_notice-title')
        self.client.logout()
        self.assertEqual(self.client.get('/plan/').status_code, 302)

    def test_upcoming_occurrences_for_repeating_chore(self):
        chore = Chore(title='Bins', due_date=self.today, repeat='weekly', creator=self.member)
        self.assertEqual(upcoming_occurrences(chore, self.today, count=3),
            [self.today + timedelta(days=7), self.today + timedelta(days=14), self.today + timedelta(days=21)])

    def test_upcoming_occurrences_is_empty_for_one_time_chore(self):
        chore = Chore(title='Deep clean', due_date=self.today, repeat='once', creator=self.member)
        self.assertEqual(upcoming_occurrences(chore, self.today), [])

    def test_planner_shows_repeating_chore_schedule(self):
        Chore.objects.create(title='Water plants', due_date=self.today + timedelta(days=2),
            repeat='weekly', creator=self.member)
        page = self.client.get('/plan/')
        self.assertContains(page, 'chore-upcoming')
        self.assertContains(page, 'Next:')
