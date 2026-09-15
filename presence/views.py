import json
import uuid

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from household.models import ActivityEntry, Household, bump_revision
from .models import PresenceEvent, PresenceMutation


def error(message, status=400):
    return JsonResponse({'error': message}, status=status)


@require_POST
def mutate(request):
    if not request.user.is_authenticated:
        return error('Sign in to change your presence.', 401)
    if len(request.body) > 2048:
        return error('Request too large.', 413)
    try:
        data = json.loads(request.body)
        operation_id = uuid.UUID(data['operation_id'])
        status = data['status']
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return error('Invalid request.')
    if status not in PresenceEvent.Status.values:
        return error('Choose HOME or OUT.')

    with transaction.atomic():
        Household.current()
        prior = PresenceMutation.objects.filter(operation_id=operation_id).first()
        if prior:
            if prior.actor_id != request.user.pk or prior.status != status:
                return error('Operation ID already used.', 409)
            return JsonResponse(prior.response)

        latest = PresenceEvent.objects.filter(member=request.user).order_by('-occurred_at', '-id').first()
        changed = not latest or latest.status != status
        if changed:
            PresenceEvent.objects.create(member=request.user, status=status, changed_by=request.user, source='manual')
            ActivityEntry.objects.create(actor=request.user, message=f'Marked themselves {status}')
            bump_revision()
        result = {'ok': True, 'status': status, 'changed': changed}
        PresenceMutation.objects.create(operation_id=operation_id, actor=request.user, status=status, response=result)
    return JsonResponse(result)
