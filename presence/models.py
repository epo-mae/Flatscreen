from django.conf import settings
from django.db import models


class PresenceEvent(models.Model):
    class Status(models.TextChoices):
        HOME = 'HOME', 'Home'
        OUT = 'OUT', 'Out'

    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='presence_events')
    status = models.CharField(max_length=4, choices=Status.choices)
    source = models.CharField(max_length=12, choices=[('manual', 'Manual'), ('device', 'Device')], default='manual')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='presence_changes')
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['member', '-occurred_at'])]


class PresenceMutation(models.Model):
    operation_id = models.UUIDField(unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=4, choices=PresenceEvent.Status.choices)
    response = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

