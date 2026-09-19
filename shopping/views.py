import csv
import hashlib
import json
import uuid
from contextlib import nullcontext
from datetime import timedelta
from zoneinfo import ZoneInfo
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from household.models import ActivityEntry, Household, Member, bump_revision
from household.views import current_display
from household.weather import get_weather
from .models import Mutation, ShoppingItem
from presence.models import PresenceEvent
from planning.models import CalendarEvent, Chore, DinnerPlan, HouseNotice


@require_GET
def state(request):
    # Display snapshots are filtered even when a member also happens to be signed in.
    display_mode = request.GET.get('view') == 'display'
    if display_mode:
        if not current_display(request):
            return JsonResponse({'error': 'Display access expired or revoked.'}, status=403)
    elif not request.user.is_authenticated:
        return JsonResponse({'error': 'Sign in to continue.'}, status=401)
    house = Household.current()
    weather = get_weather(house)
    weather_version = weather.get('updated_at', 'unavailable')
    with nullcontext():
        etag = f'"{house.revision}-{weather_version}-{ "display" if display_mode else "member"}"'
        if request.headers.get('If-None-Match') == etag:
            response = JsonResponse({}, status=304)
        else:
            items = ShoppingItem.objects.filter(deleted_at=None).select_related('added_by', 'purchased_by').order_by('purchased', 'added_at', 'id')
            rows = []
            for item in items:
                row = {'id': item.pk, 'name': item.name, 'quantity': item.quantity, 'purchased': item.purchased, 'version': item.version}
                if not display_mode:
                    row.update(note=item.note, added_by=item.added_by.label,
                        purchased_by=item.purchased_by.label if item.purchased_by else None)
                rows.append(row)
            members = []
            for member in Member.objects.filter(is_active=True).order_by('date_joined', 'id'):
                latest = PresenceEvent.objects.filter(member=member).order_by('-occurred_at', '-id').first()
                member_data = {
                    'name': member.label,
                    'initials': member.initials,
                    'presence': latest.status if latest else 'UNKNOWN',
                }
                if not display_mode:
                    member_data.update(id=member.pk, is_self=member.pk == request.user.pk)
                members.append(member_data)
            now = timezone.now()
            local_date = now.astimezone(ZoneInfo(house.timezone)).date()
            dinners = []
            for plan in DinnerPlan.objects.filter(date__gte=local_date).select_related('cook')[:4]:
                dinners.append({
                    'date': plan.date.isoformat(),
                    'cook': plan.cook.label if plan.cook else None,
                    'meal': plan.meal,
                    'notes': plan.notes if not display_mode else '',
                    'happening': plan.is_happening,
                    'time': plan.serving_time.strftime('%H:%M') if plan.serving_time else None,
                })
            events = []
            for event in CalendarEvent.objects.filter(event_date__gte=local_date, deleted_at=None)[:3]:
                days = (event.event_date - local_date).days
                countdown = 'TODAY' if days == 0 else 'TOMORROW' if days == 1 else f'IN {days} DAYS'
                events.append({
                    'title': event.title,
                    'date': event.event_date.isoformat(),
                    'time': event.start_time.strftime('%H:%M') if event.start_time else None,
                    'category': event.get_category_display(),
                    'countdown': countdown,
                })
            active_notices = list(HouseNotice.objects.filter(deleted_at=None).filter(
                Q(expires_at=None) | Q(expires_at__gt=now)
            ).order_by('-created_at')[:20])
            active_notices.sort(key=lambda notice: notice.importance != HouseNotice.Importance.IMPORTANT)
            notices = [{
                'title': notice.title,
                'message': notice.message,
                'importance': notice.importance,
            } for notice in active_notices[:2]]
            chores = []
            chore_limit = 4 if display_mode else 20
            for chore in Chore.objects.filter(deleted_at=None, completed_at=None).select_related('assigned_to')[:chore_limit]:
                days = (chore.due_date - local_date).days
                due_label = 'OVERDUE' if days < 0 else 'TODAY' if days == 0 else 'TOMORROW' if days == 1 else chore.due_date.strftime('%a %d %b').upper()
                row = {
                    'title': chore.title,
                    'assigned_to': chore.assigned_to.label if chore.assigned_to else 'Anyone',
                    'due_date': chore.due_date.isoformat(),
                    'due_label': due_label,
                    'repeat': chore.get_repeat_display(),
                    'overdue': days < 0,
                }
                if not display_mode:
                    row.update(id=chore.pk, notes=chore.notes, assigned_to_id=chore.assigned_to_id)
                chores.append(row)
            data = {
                'revision': house.revision, 'household': house.name, 'timezone': house.timezone,
                'items': rows, 'members': members, 'dinners': dinners, 'events': events, 'notices': notices, 'chores': chores,
                'local_date': local_date.isoformat(), 'weather': weather,
            }
            response = JsonResponse(data)
        response['ETag'] = etag
        return response


@login_required
@require_GET
def export(request):
    items = ShoppingItem.objects.filter(deleted_at=None, purchased=False).order_by('added_at', 'id')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="shopping-list.csv"'
    writer = csv.writer(response)
    writer.writerow(['Quantity', 'Item', 'Note'])
    for item in items:
        writer.writerow([item.quantity, item.name, item.note])
    return response


def error(message, status=400, **extra):
    return JsonResponse({'error': message, **extra}, status=status)


@require_POST
def mutate(request):
    if not request.user.is_authenticated:
        return error('Sign in to change the shopping list.', 401)
    if len(request.body) > 8192:
        return error('Request too large.', 413)
    try:
        data = json.loads(request.body)
        operation_id = uuid.UUID(data['operation_id'])
        action = data['action']
        if not isinstance(action, str):
            raise ValueError
    except (ValueError, KeyError, TypeError, AttributeError):
        return error('Invalid request.')
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    with transaction.atomic():
        Household.current()
        prior = Mutation.objects.filter(operation_id=operation_id).first()
        if prior:
            if prior.actor_id != request.user.pk or prior.fingerprint != fingerprint:
                return error('Operation ID already used.', 409)
            return JsonResponse(prior.response)
        result = {}
        if action == 'add':
            name = ' '.join(str(data.get('name', '')).split())
            note = str(data.get('note', '')).strip()
            quantity = data.get('quantity', 1)
            if not name or len(name) > 100 or len(note) > 240 or type(quantity) is not int or not 1 <= quantity <= 999:
                return error('Enter a name, a quantity from 1 to 999, and a note under 241 characters.')
            normalized = name.casefold()
            existing = ShoppingItem.objects.filter(normalized_name=normalized, purchased=False, deleted_at=None).first()
            if existing and data.get('duplicate') not in ('merge', 'separate'):
                return error(f'{existing.name} is already on the list. Increase its quantity?', 409, duplicate=True)
            if existing and data.get('duplicate') == 'merge':
                if existing.quantity + quantity > 999:
                    return error('Combined quantity cannot exceed 999.')
                existing.quantity += quantity
                existing.version += 1
                existing.save(update_fields=['quantity', 'version'])
                item = existing
            else:
                item = ShoppingItem.objects.create(name=name, normalized_name=normalized, quantity=quantity, note=note, added_by=request.user)
            description = f'Added {quantity} × {name}'
            result['item_id'] = item.pk
        elif action in ('clear_all', 'clear_purchased'):
            if data.get('confirmed') is not True:
                return error('Confirm before clearing items.')
            if data.get('revision') != Household.current().revision:
                return error('The list changed. Review it and confirm again.', 409)
            items = ShoppingItem.objects.filter(deleted_at=None)
            if action == 'clear_purchased':
                items = items.filter(purchased=True)
            from django.db.models import F
            count = items.update(deleted_at=timezone.now(), version=F('version') + 1)
            description = f'Cleared {count} shopping items'
        else:
            if type(data.get('id')) is not int:
                return error('Choose a valid item.')
            item = ShoppingItem.objects.filter(pk=data['id']).first()
            if not item:
                return error('Item not found.', 404)
            if type(data.get('version')) is not int or item.version != data['version']:
                return error('Someone changed this item. Review the latest version and try again.', 409)
            if item.deleted_at and action != 'restore':
                return error('This item has been removed.', 409)
            if action == 'quantity':
                delta = data.get('delta')
                if type(delta) is not int or delta not in (-1, 1) or not 1 <= item.quantity + delta <= 999:
                    return error('Quantity must stay between 1 and 999.')
                item.quantity += delta
                description = f'Changed quantity of {item.name}'
            elif action == 'purchase':
                if type(data.get('purchased')) is not bool:
                    return error('Choose a purchased state.')
                item.purchased = data['purchased']
                item.purchased_by = request.user if item.purchased else None
                item.purchased_at = timezone.now() if item.purchased else None
                description = f'{"Purchased" if item.purchased else "Reopened"} {item.name}'
            elif action == 'edit':
                name = ' '.join(str(data.get('name', '')).split())
                note = str(data.get('note', '')).strip()
                if not name or len(name) > 100 or len(note) > 240:
                    return error('Enter a name under 101 characters and a note under 241 characters.')
                item.name, item.normalized_name, item.note = name, name.casefold(), note
                description = f'Edited {name}'
            elif action == 'delete':
                item.deleted_at = timezone.now()
                description = f'Removed {item.name}'
                result['undo'] = {'id': item.pk, 'version': item.version + 1}
            elif action == 'restore':
                if not item.deleted_at or item.deleted_at < timezone.now() - timedelta(days=7):
                    return error('This item is no longer available to restore.', 409)
                item.deleted_at = None
                description = f'Restored {item.name}'
            else:
                return error('Unknown action.')
            item.version += 1
            item.save()
        ActivityEntry.objects.create(actor=request.user, message=description[:250])
        bump_revision()
        result['ok'] = True
        Mutation.objects.create(operation_id=operation_id, actor=request.user, fingerprint=fingerprint, response=result)
    return JsonResponse(result)
