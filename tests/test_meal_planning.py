import json
import uuid
from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.test import Client, TestCase
from django.utils import timezone
from household.models import ActivityEntry, Household, Member
from planning.models import DinnerPlan, DinnerPlanIngredient, SavedDinner, SavedDinnerIngredient
from shopping.known import known_suggestions
from shopping.models import KnownItem, ShoppingItem


class MealPlanningTests(TestCase):
    def setUp(self):
        weather = {'available': True, 'location': 'Auckland', 'temperature': 17, 'feels_like': 16,
                   'high': 20, 'low': 12, 'uv': 5.2, 'description': 'Partly cloudy', 'alerts': [],
                   'updated_at': '2026-09-15T00:00:00+00:00', 'stale': False}
        self.weather_patcher = patch('shopping.views.get_weather', return_value=weather)
        self.weather_patcher.start(); self.addCleanup(self.weather_patcher.stop)
        self.house = Household.current()
        self.member = Member.objects.create_user(username='sam', display_name='Sam', password='Household-test-4821')
        self.cook = Member.objects.create_user(username='riley', display_name='Riley', password='Household-test-5932')
        self.client.force_login(self.member)
        session = self.client.session
        session['access_version'] = self.member.access_version
        session.save()

    def local_today(self):
        return timezone.now().astimezone(ZoneInfo(self.house.timezone)).date().isoformat()

    def meal(self, payload=None, **kwargs):
        base = {'action': 'plan', 'date': self.local_today(), 'name': 'Tacos', 'cook_id': self.cook.pk,
                'ingredients': [{'name': 'Lettuce', 'quantity': 1, 'category': 'produce'},
                                {'name': 'Tortillas', 'quantity': 12, 'category': 'pantry'}]}
        base.update(payload or {})
        base.update(kwargs)
        base.setdefault('operation_id', str(uuid.uuid4()))
        return self.client.post('/api/dinners/', data=json.dumps(base), content_type='application/json')

    def shopping_mutation(self, payload, client=None):
        payload.setdefault('operation_id', str(uuid.uuid4()))
        return (client or self.client).post('/api/shopping/', data=json.dumps(payload), content_type='application/json')

    def display_client(self):
        from household.models import DisplayDevice
        device = DisplayDevice.objects.create(approved=True, expires_at=timezone.now() + timedelta(minutes=10))
        client = Client()
        session = client.session
        session['display_id'] = device.pk
        session.save()
        return client

    def test_plan_creates_template_occurrence_cook_and_memory(self):
        response = self.meal()
        self.assertEqual(response.status_code, 200, response.content)
        plan = DinnerPlan.objects.get()
        self.assertEqual(plan.meal, 'Tacos')
        self.assertEqual(plan.cook, self.cook)
        self.assertTrue(plan.is_happening)
        self.assertIsNotNone(plan.saved_dinner)
        self.assertEqual(SavedDinnerIngredient.objects.count(), 2)
        self.assertEqual(DinnerPlanIngredient.objects.count(), 2)
        self.assertEqual(plan.saved_dinner.uses, 1)
        lettuce = KnownItem.objects.get(normalized_name='lettuce')
        self.assertEqual(lettuce.category, 'produce')
        self.assertEqual(lettuce.canonical_name, 'Lettuce')
        self.assertEqual(known_suggestions(12)[0]['name'], 'Tortillas')
        self.assertIsNotNone(self.house.revision)
        self.assertTrue(ActivityEntry.objects.filter(message__startswith='Planned dinner').exists())

    def test_plan_is_idempotent_on_retry(self):
        operation_id = str(uuid.uuid4())
        first = self.meal(operation_id=operation_id)
        second = self.meal(operation_id=operation_id)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(DinnerPlan.objects.count(), 1)
        self.assertEqual(SavedDinner.objects.count(), 1)
        self.assertEqual(DinnerPlanIngredient.objects.count(), 2)

    def test_reusing_operation_id_with_different_body_is_rejected(self):
        operation_id = str(uuid.uuid4())
        self.meal(operation_id=operation_id)
        response = self.meal(operation_id=operation_id, name='Burritos')
        self.assertEqual(response.status_code, 409)

    def test_plan_reuses_saved_dinner_without_overwriting_template(self):
        created = self.meal().json()['plan']
        template = SavedDinner.objects.get(pk=created['saved_dinner_id'])
        changed = self.meal(name='Tacos supreme', saved_dinner_id=template.pk,
                            ingredients=[{'name': 'Lettuce', 'quantity': 2, 'category': 'produce'}])
        self.assertEqual(changed.status_code, 200, changed.content)
        template.refresh_from_db()
        self.assertEqual(SavedDinnerIngredient.objects.filter(dinner=template).count(), 2)
        plan = DinnerPlan.objects.get()
        self.assertEqual(plan.meal, 'Tacos supreme')
        self.assertEqual(DinnerPlanIngredient.objects.filter(plan=plan).count(), 1)
        self.assertEqual(template.uses, 1)

    def test_planning_same_date_upserts_instead_of_duplicating(self):
        self.meal()
        self.meal(name='Burritos')
        self.assertEqual(DinnerPlan.objects.count(), 1)
        self.assertEqual(DinnerPlan.objects.get().meal, 'Burritos')

    def test_update_saved_replaces_template_and_name(self):
        created = self.meal().json()['plan']
        response = self.client.post('/api/dinners/', data=json.dumps({
            'operation_id': str(uuid.uuid4()), 'action': 'update_saved',
            'saved_dinner_id': created['saved_dinner_id'], 'name': 'Loaded tacos',
            'ingredients': [{'name': 'Sour cream', 'quantity': 1, 'category': 'dairy'}],
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        template = SavedDinner.objects.get(pk=created['saved_dinner_id'])
        self.assertEqual(template.name, 'Loaded tacos')
        self.assertEqual(list(template.ingredients.values_list('name', flat=True)), ['Sour cream'])

    def test_add_shopping_merges_within_same_dinner_and_separates_across_dinners(self):
        plan = self.meal().json()['plan']
        first = self.client.post('/api/dinners/', data=json.dumps({
            'operation_id': str(uuid.uuid4()), 'action': 'add_shopping', 'plan_id': plan['id'],
            'ingredients': [{'name': 'Lettuce', 'quantity': 1, 'category': 'produce'},
                            {'name': 'Tortillas', 'quantity': 12, 'category': 'pantry'}],
        }), content_type='application/json')
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(ShoppingItem.objects.count(), 2)
        second = self.client.post('/api/dinners/', data=json.dumps({
            'operation_id': str(uuid.uuid4()), 'action': 'add_shopping', 'plan_id': plan['id'],
            'ingredients': [{'name': 'Lettuce', 'quantity': 2, 'category': 'produce'}],
        }), content_type='application/json')
        merged = second.json()['added'][0]
        self.assertTrue(merged['merged'])
        self.assertEqual(second.json()['count'], 1)
        self.assertEqual(ShoppingItem.objects.count(), 2)
        other_date = (timezone.now().astimezone(ZoneInfo(self.house.timezone)).date() + timedelta(days=1)).isoformat()
        other_plan = self.meal(date=other_date, name='Salads').json()['plan']
        third = self.client.post('/api/dinners/', data=json.dumps({
            'operation_id': str(uuid.uuid4()), 'action': 'add_shopping', 'plan_id': other_plan['id'],
            'ingredients': [{'name': 'Lettuce', 'quantity': 1, 'category': 'produce'}],
        }), content_type='application/json')
        self.assertFalse(third.json()['added'][0]['merged'])
        self.assertEqual(ShoppingItem.objects.count(), 3)
        self.assertEqual(ShoppingItem.objects.filter(dinner_plan_id=other_plan['id']).count(), 1)

    def test_state_exposes_category_and_meal_grouping_for_members(self):
        plan = self.meal().json()['plan']
        self.client.post('/api/dinners/', data=json.dumps({
            'operation_id': str(uuid.uuid4()), 'action': 'add_shopping', 'plan_id': plan['id'],
        }), content_type='application/json')
        rows = self.client.get('/api/state/').json()['items']
        lettuce = next(row for row in rows if row['name'] == 'Lettuce')
        self.assertEqual(lettuce['category'], 'produce')
        self.assertEqual(lettuce['dinner_id'], plan['id'])
        self.assertEqual(lettuce['dinner'], 'Tacos')
        self.assertEqual(lettuce['dinner_cook'], 'Riley')
        state = self.client.get('/api/state/').json()
        self.assertEqual(state['categories'][0], 'produce')
        self.assertTrue(state['suggestions'])

    def test_display_dinner_reports_ingredient_and_shopping_state(self):
        plan = self.meal().json()['plan']
        state = self.display_client().get('/api/state/?view=display').json()
        tonight = next(dinner for dinner in state['dinners'] if dinner['date'] == self.local_today())
        self.assertEqual(tonight['ingredients'], 2)
        self.assertEqual(tonight['shopping_pending'], 2)
        self.assertNotIn('suggestions', state)
        self.client.post('/api/dinners/', data=json.dumps({
            'operation_id': str(uuid.uuid4()), 'action': 'add_shopping', 'plan_id': plan['id'],
        }), content_type='application/json')
        updated = self.display_client().get('/api/state/?view=display').json()
        tonight = next(dinner for dinner in updated['dinners'] if dinner['date'] == self.local_today())
        self.assertEqual(tonight['shopping_pending'], 0)

    def test_manual_shopping_remembers_category_for_future_ingredients(self):
        response = self.shopping_mutation({'action': 'add', 'name': 'Milk', 'quantity': 1, 'category': 'dairy'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(KnownItem.objects.get(normalized_name='milk').category, 'dairy')
        self.meal(ingredients=[{'name': 'Milk', 'quantity': 1, 'category': 'other'}])
        ingredient = DinnerPlanIngredient.objects.get(name='Milk')
        self.assertEqual(ingredient.category, 'dairy')
        self.assertEqual(ShoppingItem.objects.get(name='Milk').category, 'dairy')

    def test_manual_add_duplicate_prompt_still_applies_outside_dinners(self):
        self.shopping_mutation({'action': 'add', 'name': 'Milk', 'quantity': 1})
        response = self.shopping_mutation({'action': 'add', 'name': 'Milk', 'quantity': 1})
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()['duplicate'])
        merge = self.shopping_mutation({'action': 'add', 'name': 'Milk', 'quantity': 1, 'duplicate': 'merge'})
        self.assertEqual(merge.status_code, 200, merge.content)
        self.assertEqual(ShoppingItem.objects.get().quantity, 2)

    def test_plan_validation_rejects_bad_input(self):
        deactivated = Member.objects.create_user(username='gone', display_name='Gone', password='Household-test-1211')
        deactivated.is_active = False
        deactivated.save()
        cases = [
            self.meal(cook_id=deactivated.pk),                      # cook must be an active member
            self.meal(cook_id=99999),                               # cook must exist and be active
            self.meal(ingredients=[{'name': 'X', 'quantity': 1, 'category': 'nope'}]),
            self.meal(ingredients=[{'name': '', 'quantity': 1}]),
            self.meal(ingredients=[{'name': 'X', 'quantity': 0}]),
            self.meal(saved_dinner_id=99999),
            self.meal(date='not-a-date'),
            self.meal(serving_time='25:00'),
            self.meal(name='x' * 121),
        ]
        for response in cases:
            self.assertEqual(response.status_code, 400, response.content)

    def test_add_shopping_validation(self):
        self.assertEqual(self.client.post('/api/dinners/', data=json.dumps({
            'operation_id': str(uuid.uuid4()), 'action': 'add_shopping', 'plan_id': 99999,
        }), content_type='application/json').status_code, 400)
        unauthenticated = Client()
        self.assertEqual(unauthenticated.post('/api/dinners/', data=json.dumps({
            'operation_id': str(uuid.uuid4()), 'action': 'plan', 'date': self.local_today(),
        }), content_type='application/json').status_code, 401)

    def test_planner_page_renders_saved_dinners_and_datalist(self):
        self.meal()
        page = self.client.get('/plan/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Tacos')
        self.assertContains(page, 'dinner-data')
        self.assertContains(page, 'ingredient-suggestions')