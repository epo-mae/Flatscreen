import hashlib
import secrets
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import HouseholdForm, MemberForm, WeatherLocationForm
from .models import AccessAttempt, ActivityEntry, DisplayDevice, Household, Member, WeatherSnapshot, bump_revision


def limited(request, purpose, maximum=10):
    key = hashlib.sha256(f'{purpose}:{request.META.get("REMOTE_ADDR", "")}'.encode()).hexdigest()
    with transaction.atomic():
        AccessAttempt.objects.filter(created_at__lt=timezone.now() - timedelta(minutes=15)).delete()
        if AccessAttempt.objects.filter(key=key).count() >= maximum:
            return True
        AccessAttempt.objects.create(key=key)
    return False


def establish_login(request, user):
    login(request, user)
    request.session['access_version'] = user.access_version


@require_http_methods(['GET', 'POST'])
def setup(request):
    if not settings.LOCAL_SETUP or request.META.get('REMOTE_ADDR') not in ('127.0.0.1', '::1'):
        return HttpResponseForbidden('Initial setup is available only on the development computer. Use createsuperuser in production.')
    if Member.objects.exists():
        return redirect('login')
    member_form = MemberForm(request.POST or None, initial={'role': 'admin'})
    house_form = HouseholdForm(request.POST or None)
    if request.method == 'POST' and member_form.is_valid() and house_form.is_valid():
        with transaction.atomic():
            if Member.objects.exists():
                return redirect('login')
            user = member_form.save(commit=False)
            user.role = 'admin'
            user.save()
            household = house_form.save(commit=False)
            household.pk = 1
            household.save()
        establish_login(request, user)
        return redirect('home')
    return render(request, 'setup.html', {'member_form': member_form, 'house_form': house_form})


@require_http_methods(['GET', 'POST'])
def sign_in(request):
    if not Member.objects.exists() and settings.LOCAL_SETUP:
        return redirect('setup')
    form = AuthenticationForm(request, data=request.POST or None)
    form.fields['username'].label = 'Username (not display name)'
    if request.method == 'POST':
        if limited(request, 'login'):
            return render(request, 'login.html', {'form': form, 'rate_error': 'Too many attempts. Try again in 15 minutes.'}, status=429)
        if form.is_valid():
            establish_login(request, form.get_user())
            return redirect('home')
    return render(request, 'login.html', {'form': form})


@require_POST
def sign_out(request):
    logout(request)
    return redirect('login')


@login_required
def personal(request):
    Household.current()
    return render(request, 'personal.html')


@login_required
@require_http_methods(['GET', 'POST'])
def settings_page(request):
    if not request.user.is_house_admin:
        return HttpResponseForbidden('Administrator access required.')
    house = Household.current()
    house_form = HouseholdForm(instance=house)
    weather_form = WeatherLocationForm(initial={'location': house.weather_location})
    member_form = MemberForm()
    if request.method == 'POST':
        action = request.POST.get('action')
        with transaction.atomic():
            if action == 'household':
                house_form = HouseholdForm(request.POST, instance=house)
                if house_form.is_valid():
                    house_form.save()
                    ActivityEntry.objects.create(actor=request.user, message='Updated household settings')
                    bump_revision()
                    messages.success(request, 'Household settings saved.')
                    return redirect('settings')
            elif action == 'weather':
                weather_form = WeatherLocationForm(request.POST)
                if weather_form.is_valid():
                    match = weather_form.match
                    house.weather_location = match['name']
                    house.weather_latitude = match['latitude']
                    house.weather_longitude = match['longitude']
                    house.weather_enabled = True
                    house.save(update_fields=['weather_location', 'weather_latitude', 'weather_longitude', 'weather_enabled'])
                    WeatherSnapshot.objects.filter(pk=1).update(fetched_at=None, failed_at=None)
                    ActivityEntry.objects.create(actor=request.user, message=f'Enabled weather for {house.weather_location}')
                    bump_revision()
                    messages.success(request, f'Weather location set to {house.weather_location}.')
                    return redirect('settings')
            elif action == 'member':
                member_form = MemberForm(request.POST)
                if member_form.is_valid():
                    member = member_form.save()
                    ActivityEntry.objects.create(actor=request.user, message=f'Added member {member.label}')
                    bump_revision()
                    messages.success(request, f'{member.label} created. Their sign-in username is {member.username}. Share their credentials privately.')
                    return redirect('settings')
            elif action == 'toggle_member':
                member = Member.objects.filter(pk=request.POST.get('member_id')).first()
                if not member or member.pk == request.user.pk:
                    messages.error(request, 'You cannot deactivate your own account here.')
                else:
                    member.is_active = not member.is_active
                    member.access_version += 1
                    member.save(update_fields=['is_active', 'access_version'])
                    ActivityEntry.objects.create(actor=request.user, message=f'{"Activated" if member.is_active else "Deactivated"} {member.label}')
                    bump_revision()
                return redirect('settings')
            elif action == 'pair':
                if limited(request, 'approve_display', 10):
                    messages.error(request, 'Too many pairing attempts. Wait 15 minutes.')
                else:
                    code = request.POST.get('code', '').replace(' ', '').strip()
                    device = DisplayDevice.objects.filter(pairing_hash=hashlib.sha256(code.encode()).hexdigest(), approved=False, revoked=False, expires_at__gt=timezone.now()).first()
                    if not device:
                        messages.error(request, 'That code is invalid or expired. Generate a new code on the display.')
                    else:
                        device.approved = True
                        device.pairing_hash = None
                        device.name = request.POST.get('device_name', '').strip()[:60] or 'Living room'
                        device.save()
                        ActivityEntry.objects.create(actor=request.user, message=f'Paired display {device.name}')
                        messages.success(request, 'Display paired. It will connect automatically.')
                return redirect('settings')
            elif action == 'revoke':
                device = DisplayDevice.objects.filter(pk=request.POST.get('device_id')).first()
                if device:
                    device.revoked = True
                    device.save(update_fields=['revoked'])
                    ActivityEntry.objects.create(actor=request.user, message=f'Revoked display {device.name}')
                return redirect('settings')
    return render(request, 'settings.html', {'house_form': house_form, 'weather_form': weather_form, 'member_form': member_form,
        'members': Member.objects.order_by('date_joined'), 'devices': DisplayDevice.objects.filter(approved=True, revoked=False),
        'activities': ActivityEntry.objects.select_related('actor').order_by('-created_at')[:15]})


def current_display(request):
    return DisplayDevice.objects.filter(pk=request.session.get('display_id'), approved=True, revoked=False).first()


@ensure_csrf_cookie
@require_GET
def display(request):
    if current_display(request):
        return render(request, 'display.html', {'display_mode': 'display'})
    device = DisplayDevice.objects.filter(pk=request.session.get('display_id'), revoked=False, approved=False, expires_at__gt=timezone.now()).first()
    return render(request, 'pair.html', {'pair_code': request.session.get('pair_code') if device else None})


@require_POST
def pair_display(request):
    if limited(request, 'create_display', 10):
        return HttpResponse('Too many pairing attempts. Try again in 15 minutes.', status=429)
    code = str(secrets.randbelow(10**8)).zfill(8)
    device = DisplayDevice.objects.create(pairing_hash=hashlib.sha256(code.encode()).hexdigest(), expires_at=timezone.now() + timedelta(minutes=10))
    request.session.cycle_key()
    request.session['display_id'] = device.pk
    request.session['pair_code'] = code
    request.session.set_expiry(60 * 60 * 24 * 365)
    return redirect('display')


@require_GET
def offline_display(request):
    return render(request, 'display.html', {'offline_shell': True, 'display_mode': 'display'})


@login_required
@require_GET
def display_preview(request):
    return render(request, 'display.html', {'display_mode': 'preview'})


@require_GET
def display_worker(request):
    return HttpResponse((settings.BASE_DIR / 'static' / 'js' / 'display-sw.js').read_text(), content_type='application/javascript')


@require_GET
def health(request):
    Household.objects.filter(pk=1).exists()
    return JsonResponse({'status': 'ok'})
