import hashlib
import json
import uuid
from calendar import monthrange
from datetime import time as dtime
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from household.models import ActivityEntry, Household, Member, bump_revision
from shopping.known import add_shopping_item, known_suggestions, normalize_name, remember_item, resolve_category
from shopping.models import ItemCategory
from .forms import CalendarEventForm, ChoreForm, DinnerPlanForm, HouseNoticeForm
from .models import CalendarEvent, Chore, ChoreCompletion, DinnerPlan, DinnerPlanIngredient, HouseNotice, PlanningMutation, SavedDinner, SavedDinnerIngredient


def _api_error(message, status=400, **extra):
    return JsonResponse({'error': message, **extra}, status=status)


def _clean_ingredients(raw):
    if not isinstance(raw, list):
        raise ValueError('Ingredients must be a list.')
    cleaned = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError('Invalid ingredient.')
        name = ' '.join(str(entry.get('name', '')).split())
        quantity = entry.get('quantity', 1)
        category = entry.get('category') or None
        if not name or len(name) > 100:
            raise ValueError('Each ingredient needs a name under 101 characters.')
        if type(quantity) is not int or not 1 <= quantity <= 999:
            raise ValueError('Each ingredient quantity must be from 1 to 999.')
        if category and category not in ItemCategory.values:
            raise ValueError('Choose a known category.')
        cleaned.append({'name': name, 'quantity': quantity, 'category': category})
    return cleaned


def _parse_time(value):
    if value in (None, ''):
        return None
    if not isinstance(value, str):
        raise ValueError('Choose a valid time.')
    try:
        hours, minutes = value.split(':')
        parsed = dtime(int(hours), int(minutes))
    except (ValueError, TypeError):
        raise ValueError('Choose a valid time.')
    return parsed


def _clean_date(value):
    try:
        from datetime import date as date_type
        return date_type.fromisoformat(value)
    except ValueError:
        raise ValueError('Choose a valid date.')


@require_http_methods(['POST'])
def dinner_api(request):
    """JSON endpoint for the dinner planner and its add-to-shopping flow.

    Mirrors the shopping mutation API: every request carries an operation_id so
    retries are safe and idempotent. It exists alongside /api/shopping/ because a
    dinner save bundles a plan, its ingredients and optionally a whole shopping
    batch into one atomic unit.
    """
    if not request.user.is_authenticated:
        return _api_error('Sign in to plan dinner.', 401)
    if len(request.body) > 16384:
        return _api_error('Request too large.', 413)
    try:
        data = json.loads(request.body)
        operation_id = uuid.UUID(data['operation_id'])
        action = data['action']
        if not isinstance(action, str):
            raise ValueError
    except (ValueError, KeyError, TypeError, AttributeError):
        return _api_error('Invalid request.')
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    with transaction.atomic():
        Household.current()
        prior = PlanningMutation.objects.filter(operation_id=operation_id).first()
        if prior:
            if prior.actor_id != request.user.pk or prior.fingerprint != fingerprint:
                return _api_error('Operation ID already used.', 409)
            return JsonResponse(prior.response)
        result = {}
        try:
            if action == 'plan':
                plan_date = _clean_date(data.get('date') or local_today().isoformat())
                name = ' '.join(str(data.get('name', '')).split())
                if len(name) > 120:
                    raise ValueError('Dinner name must be under 121 characters.')
                notes = str(data.get('notes', '')).strip()
                if len(notes) > 240:
                    raise ValueError('Notes must be under 241 characters.')
                serving_time = _parse_time(data.get('serving_time'))
                ingredients = _clean_ingredients(data.get('ingredients', []))
                is_happening = data.get('is_happening') is not False
                cook = None
                cook_id = data.get('cook_id')
                if cook_id is not None:
                    if type(cook_id) is not int:
                        raise ValueError('Choose a cook.')
                    cook = Member.objects.filter(pk=cook_id, is_active=True).first()
                    if not cook:
                        raise ValueError('Choose a cook from active household members.')
                saved = None
                saved_dinner_id = data.get('saved_dinner_id')
                if saved_dinner_id is not None:
                    if type(saved_dinner_id) is not int:
                        raise ValueError('Choose a saved dinner.')
                    saved = SavedDinner.objects.filter(pk=saved_dinner_id).first()
                    if not saved:
                        raise ValueError('That saved dinner no longer exists.')
                plan, created = DinnerPlan.objects.get_or_create(date=plan_date, defaults={'created_by': request.user, 'updated_by': request.user})
                prior_template = plan.saved_dinner_id
                plan.cook = cook
                plan.meal = name
                plan.notes = notes
                plan.serving_time = serving_time
                plan.is_happening = is_happening
                plan.updated_by = request.user
                if saved is None and name:
                    saved = SavedDinner.objects.create(name=name, created_by=request.user)
                    for row in ingredients:
                        category = resolve_category(row['name'], row['category'])
                        remember_item(row['name'], row['category'])
                        SavedDinnerIngredient.objects.create(dinner_id=saved.pk, name=row['name'],
                                                             normalized_name=normalize_name(row['name']),
                                                             quantity=row['quantity'], category=category)
                    plan.saved_dinner = saved
                elif saved is not None and data.get('save_template'):
                    saved.name = name or saved.name
                    saved.save()
                    saved.ingredients.all().delete()
                    for row in ingredients:
                        category = resolve_category(row['name'], row['category'])
                        remember_item(row['name'], row['category'])
                        SavedDinnerIngredient.objects.create(dinner_id=saved.pk, name=row['name'],
                                                             normalized_name=normalize_name(row['name']),
                                                             quantity=row['quantity'], category=category)
                    plan.saved_dinner = saved
                else:
                    plan.saved_dinner = saved
                plan.save()
                if plan.saved_dinner_id and plan.saved_dinner_id != prior_template:
                    SavedDinner.objects.filter(pk=plan.saved_dinner_id).update(uses=F('uses') + 1)
                plan.ingredients.all().delete()
                for row in ingredients:
                    category = resolve_category(row['name'], row['category'])
                    remember_item(row['name'], row['category'])
                    DinnerPlanIngredient.objects.create(plan_id=plan.pk, name=row['name'],
                                                        normalized_name=normalize_name(row['name']),
                                                        quantity=row['quantity'], category=category)
                result['plan'] = {
                    'id': plan.pk, 'date': plan.date.isoformat(), 'meal': plan.meal,
                    'cook': plan.cook.label if plan.cook else None, 'cook_id': plan.cook_id,
                    'saved_dinner_id': plan.saved_dinner_id, 'created': created,
                    'ingredients': [{'name': i.name, 'quantity': i.quantity, 'category': i.category} for i in plan.ingredients.all()],
                }
                description = f'Planned dinner for {plan.date.strftime("%d %b").lstrip("0")}'
            elif action == 'add_shopping':
                plan_id = data.get('plan_id')
                if type(plan_id) is not int:
                    raise ValueError('Choose a dinner plan.')
                plan = DinnerPlan.objects.filter(pk=plan_id).first()
                if not plan:
                    raise ValueError('That dinner plan no longer exists.')
                rows = data.get('ingredients')
                if rows is None:
                    rows = [{'name': i.name, 'quantity': i.quantity} for i in plan.ingredients.all()]
                rows = _clean_ingredients(rows)
                added = []
                for row in rows:
                    item, merged = add_shopping_item(request.user, name=row['name'], quantity=row['quantity'],
                                                     category=row['category'], dinner_plan=plan)
                    added.append({'name': item.name, 'quantity': item.quantity, 'category': item.category, 'merged': merged})
                result['added'] = added
                result['count'] = len(added)
                description = f'Added {len(added)} item{"s" if len(added) != 1 else ""} from the {"meal" if plan.meal else "dinner plan"} to shopping'
            elif action == 'update_saved':
                saved_id = data.get('saved_dinner_id')
                if type(saved_id) is not int:
                    raise ValueError('Choose a saved dinner.')
                saved = SavedDinner.objects.select_for_update().filter(pk=saved_id).first()
                if not saved:
                    raise ValueError('That saved dinner no longer exists.')
                name = ' '.join(str(data.get('name', '')).split())
                if not name or len(name) > 120:
                    raise ValueError('Enter a saved dinner name under 121 characters.')
                ingredients = _clean_ingredients(data.get('ingredients', []))
                saved.name = name
                saved.save()
                saved.ingredients.all().delete()
                for row in ingredients:
                    category = resolve_category(row['name'], row['category'])
                    remember_item(row['name'], row['category'])
                    SavedDinnerIngredient.objects.create(dinner_id=saved.pk, name=row['name'],
                                                         normalized_name=normalize_name(row['name']),
                                                         quantity=row['quantity'], category=category)
                result['saved_dinner'] = {
                    'id': saved.pk, 'name': saved.name,
                    'ingredients': [{'name': i.name, 'quantity': i.quantity, 'category': i.category} for i in saved.ingredients.all()],
                }
                description = f'Updated saved dinner {saved.name}'
            else:
                return _api_error('Unknown action.')
        except ValueError as exc:
            return _api_error(str(exc))
        ActivityEntry.objects.create(actor=request.user, message=description[:250])
        bump_revision()
        result['ok'] = True
        PlanningMutation.objects.create(operation_id=operation_id, actor=request.user, fingerprint=fingerprint, response=result)
    return JsonResponse(result)


def local_today():
    house = Household.current()
    return timezone.now().astimezone(ZoneInfo(house.timezone)).date()


def _advance_once(chore, due):
    if chore.repeat == Chore.Repeat.DAILY:
        return due + timedelta(days=1)
    if chore.repeat == Chore.Repeat.WEEKLY:
        return due + timedelta(days=7)
    if chore.repeat == Chore.Repeat.FORTNIGHTLY:
        return due + timedelta(days=14)
    if chore.repeat == Chore.Repeat.MONTHLY:
        month = due.month + 1
        year = due.year + (month > 12)
        month = 1 if month > 12 else month
        return due.replace(year=year, month=month, day=min(due.day, monthrange(year, month)[1]))
    return due


def next_due_date(chore, today):
    due = chore.due_date
    first_advance = True
    while first_advance or due <= today:
        first_advance = False
        due = _advance_once(chore, due)
    return due


def upcoming_occurrences(chore, today, count=4):
    if chore.repeat == Chore.Repeat.ONCE:
        return []
    dates = []
    due = chore.due_date
    for _ in range(count):
        if due <= today:
            due = next_due_date(chore, today)
        if due not in dates:
            dates.append(due)
        due = _advance_once(chore, due)
    return dates


@login_required
@require_http_methods(['GET', 'POST'])
def planner(request):
    today = local_today()
    editing_event = None
    editing_chore = None
    event_id = request.GET.get('event', '')
    if event_id.isdigit():
        editing_event = CalendarEvent.objects.filter(pk=int(event_id), deleted_at=None).first()
    chore_id = request.GET.get('chore', '')
    if chore_id.isdigit():
        editing_chore = Chore.objects.filter(pk=int(chore_id), deleted_at=None).first()
    dinner_form = DinnerPlanForm(initial={'date': today, 'is_happening': True}, prefix='dinner')
    event_form = CalendarEventForm(instance=editing_event, initial={} if editing_event else {'event_date': today}, prefix='event')
    notice_form = HouseNoticeForm(prefix='notice')
    chore_form = ChoreForm(instance=editing_chore, initial={} if editing_chore else {'due_date': today}, prefix='chore')

    if request.method == 'POST':
        action = request.POST.get('action')
        with transaction.atomic():
            if action == 'dinner':
                dinner_form = DinnerPlanForm(request.POST, prefix='dinner')
                if dinner_form.is_valid():
                    existing = DinnerPlan.objects.filter(date=dinner_form.cleaned_data['date']).first()
                    if existing:
                        dinner_form = DinnerPlanForm(request.POST, instance=existing, prefix='dinner')
                        dinner_form.is_valid()
                    plan = dinner_form.save(commit=False)
                    if not plan.pk:
                        plan.created_by = request.user
                    plan.updated_by = request.user
                    plan.save()
                    date_label = plan.date.strftime('%d %b').lstrip('0')
                    ActivityEntry.objects.create(actor=request.user, message=f'Updated dinner for {date_label}')
                    bump_revision()
                    messages.success(request, 'Dinner plan saved.')
                    return redirect('planner')
            elif action == 'event':
                event_id = request.POST.get('event_id', '')
                existing = CalendarEvent.objects.filter(pk=int(event_id), deleted_at=None).first() if event_id.isdigit() else None
                event_form = CalendarEventForm(request.POST, instance=existing, prefix='event')
                if event_form.is_valid():
                    event = event_form.save(commit=False)
                    if not event.pk:
                        event.creator = request.user
                    event.save()
                    ActivityEntry.objects.create(actor=request.user, message=f'{"Updated" if existing else "Added"} event {event.title}')
                    bump_revision()
                    messages.success(request, 'Event saved.')
                    return redirect('planner')
            elif action == 'notice':
                notice_form = HouseNoticeForm(request.POST, prefix='notice')
                if notice_form.is_valid():
                    notice = notice_form.save(commit=False)
                    notice.creator = request.user
                    hours = notice_form.cleaned_data['expires_in']
                    notice.expires_at = timezone.now() + timedelta(hours=int(hours)) if hours else None
                    notice.save()
                    ActivityEntry.objects.create(actor=request.user, message=f'Posted notice {notice.title}')
                    bump_revision()
                    messages.success(request, 'Notice posted.')
                    return redirect('planner')
            elif action == 'chore':
                chore_id = request.POST.get('chore_id', '')
                existing = Chore.objects.filter(pk=int(chore_id), deleted_at=None).first() if chore_id.isdigit() else None
                chore_form = ChoreForm(request.POST, instance=existing, prefix='chore')
                if chore_form.is_valid():
                    chore = chore_form.save(commit=False)
                    if not chore.pk:
                        chore.creator = request.user
                    chore.save()
                    ActivityEntry.objects.create(actor=request.user, message=f'{"Updated" if existing else "Added"} chore {chore.title}')
                    bump_revision()
                    messages.success(request, 'Responsibility saved.')
                    return redirect('planner')
            elif action in ('complete_chore', 'reopen_chore', 'remove_chore'):
                record_id = request.POST.get('record_id', '')
                chore = Chore.objects.select_for_update().filter(pk=int(record_id), deleted_at=None).first() if record_id.isdigit() else None
                if chore:
                    if action == 'complete_chore' and not chore.completed_at:
                        if request.POST.get('expected_due_date') != chore.due_date.isoformat():
                            messages.info(request, 'That chore was already updated. The latest schedule is shown below.')
                            return redirect('planner')
                        completed_at = timezone.now()
                        ChoreCompletion.objects.create(chore=chore, completed_by=request.user, due_date=chore.due_date)
                        if chore.repeat == Chore.Repeat.ONCE:
                            chore.completed_at, chore.completed_by = completed_at, request.user
                            fields = ['completed_at', 'completed_by', 'updated_at']
                        else:
                            chore.due_date = next_due_date(chore, today)
                            fields = ['due_date', 'updated_at']
                        chore.save(update_fields=fields)
                        message = f'Completed chore {chore.title}'
                    elif action == 'reopen_chore' and chore.completed_at:
                        chore.completed_at, chore.completed_by = None, None
                        chore.save(update_fields=['completed_at', 'completed_by', 'updated_at'])
                        message = f'Reopened chore {chore.title}'
                    elif action == 'remove_chore':
                        chore.deleted_at = timezone.now()
                        chore.save(update_fields=['deleted_at', 'updated_at'])
                        message = f'Removed chore {chore.title}'
                    else:
                        return redirect('planner')
                    ActivityEntry.objects.create(actor=request.user, message=message)
                    bump_revision()
                    messages.success(request, 'Chore board updated.')
                return redirect('planner')
            elif action in ('remove_event', 'remove_notice'):
                model = CalendarEvent if action == 'remove_event' else HouseNotice
                record_id = request.POST.get('record_id', '')
                record = model.objects.filter(pk=int(record_id), deleted_at=None).first() if record_id.isdigit() else None
                if record:
                    record.deleted_at = timezone.now()
                    record.save(update_fields=['deleted_at'])
                    label = record.title
                    ActivityEntry.objects.create(actor=request.user, message=f'Removed {label}')
                    bump_revision()
                    messages.success(request, 'Removed from the household display.')
                return redirect('planner')

    active_chores = list(Chore.objects.filter(deleted_at=None, completed_at=None).select_related('assigned_to')[:20])
    for chore in active_chores:
        chore.upcoming = upcoming_occurrences(chore, today)
    dinner_plans = list(DinnerPlan.objects.filter(date__gte=today).select_related('cook', 'saved_dinner').prefetch_related('ingredients')[:7])
    saved_dinners = list(SavedDinner.objects.prefetch_related('ingredients').order_by('-uses', 'name'))
    recent_ids = [p.saved_dinner_id for p in DinnerPlan.objects.filter(date__lt=today, saved_dinner__isnull=False).select_related('saved_dinner').order_by('-date')[:6] if p.saved_dinner_id]
    recent_ids = list(dict.fromkeys(recent_ids))
    dinner_data = {
        'today': today.isoformat(),
        'categories': [category for category, _ in ItemCategory.choices],
        'members': [{'id': m.pk, 'name': m.label} for m in Member.objects.filter(is_active=True).order_by('date_joined', 'id')],
        'recent_ids': recent_ids,
        'saved': [{'id': s.pk, 'name': s.name, 'uses': s.uses,
                   'ingredients': [{'name': i.name, 'quantity': i.quantity, 'category': i.category} for i in s.ingredients.all()]}
                  for s in saved_dinners],
        'plans': [{'id': p.pk, 'date': p.date.isoformat(), 'meal': p.meal,
                   'cook_id': p.cook_id, 'cook': p.cook.label if p.cook else None,
                   'saved_dinner_id': p.saved_dinner_id, 'time': p.serving_time.strftime('%H:%M') if p.serving_time else None,
                   'notes': p.notes, 'happening': p.is_happening,
                   'ingredients': [{'name': i.name, 'quantity': i.quantity, 'category': i.category} for i in p.ingredients.all()]}
                  for p in dinner_plans],
        'suggestions': known_suggestions(14),
    }
    return render(request, 'planner.html', {
        'today': today,
        'dinner_form': dinner_form,
        'event_form': event_form,
        'editing_event': editing_event,
        'notice_form': notice_form,
        'chore_form': chore_form,
        'editing_chore': editing_chore,
        'chores': active_chores,
        'completed_chores': Chore.objects.filter(deleted_at=None, completed_at__gte=timezone.now() - timedelta(days=7)).select_related('assigned_to', 'completed_by').order_by('-completed_at')[:8],
        'dinners': dinner_plans,
        'saved_dinners': saved_dinners,
        'dinner_data': dinner_data,
        'dinner_suggestions': dinner_data['suggestions'],
        'events': CalendarEvent.objects.filter(event_date__gte=today, deleted_at=None)[:12],
        'notices': HouseNotice.objects.filter(deleted_at=None).filter(Q(expires_at=None) | Q(expires_at__gt=timezone.now()))[:12],
    })
