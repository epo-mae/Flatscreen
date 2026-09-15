from calendar import monthrange
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from household.models import ActivityEntry, Household, bump_revision
from .forms import CalendarEventForm, ChoreForm, DinnerPlanForm, HouseNoticeForm
from .models import CalendarEvent, Chore, ChoreCompletion, DinnerPlan, HouseNotice


def local_today():
    house = Household.current()
    return timezone.now().astimezone(ZoneInfo(house.timezone)).date()


def next_due_date(chore, today):
    due = chore.due_date
    anchor_day = due.day
    first_advance = True
    while first_advance or due <= today:
        first_advance = False
        if chore.repeat == Chore.Repeat.DAILY:
            due += timedelta(days=1)
        elif chore.repeat == Chore.Repeat.WEEKLY:
            due += timedelta(days=7)
        elif chore.repeat == Chore.Repeat.FORTNIGHTLY:
            due += timedelta(days=14)
        elif chore.repeat == Chore.Repeat.MONTHLY:
            month = due.month + 1
            year = due.year + (month > 12)
            month = 1 if month > 12 else month
            due = due.replace(year=year, month=month, day=min(anchor_day, monthrange(year, month)[1]))
        else:
            return due
    return due


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

    return render(request, 'planner.html', {
        'today': today,
        'dinner_form': dinner_form,
        'event_form': event_form,
        'editing_event': editing_event,
        'notice_form': notice_form,
        'chore_form': chore_form,
        'editing_chore': editing_chore,
        'chores': Chore.objects.filter(deleted_at=None, completed_at=None).select_related('assigned_to')[:20],
        'completed_chores': Chore.objects.filter(deleted_at=None, completed_at__gte=timezone.now() - timedelta(days=7)).select_related('assigned_to', 'completed_by').order_by('-completed_at')[:8],
        'dinners': DinnerPlan.objects.filter(date__gte=today)[:7],
        'events': CalendarEvent.objects.filter(event_date__gte=today, deleted_at=None)[:12],
        'notices': HouseNotice.objects.filter(deleted_at=None).filter(Q(expires_at=None) | Q(expires_at__gt=timezone.now()))[:12],
    })
