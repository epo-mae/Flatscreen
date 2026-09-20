from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F

from .appearance import PRESET_CHOICES, resolve_config


class Member(AbstractUser):
    display_name = models.CharField(max_length=60)
    role = models.CharField(max_length=10, choices=[('member', 'Member'), ('admin', 'Administrator')], default='member')
    access_version = models.PositiveIntegerField(default=1)

    @property
    def is_house_admin(self):
        return self.is_active and (self.role == 'admin' or self.is_superuser)

    @property
    def label(self):
        return self.display_name or self.username

    @property
    def initials(self):
        return ''.join(part[0] for part in self.label.split()[:2]).upper()


class Household(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    name = models.CharField(max_length=80, default='Our household')
    timezone = models.CharField(max_length=64, default='Pacific/Auckland')
    weather_location = models.CharField(max_length=100, default='Auckland')
    weather_latitude = models.DecimalField(max_digits=8, decimal_places=5, default=-36.84846)
    weather_longitude = models.DecimalField(max_digits=8, decimal_places=5, default=174.76334)
    weather_enabled = models.BooleanField(default=False)
    base_preset = models.CharField(max_length=24, choices=PRESET_CHOICES, default='classic')
    appearance_overrides = models.JSONField(default=dict, blank=True)
    revision = models.PositiveBigIntegerField(default=1)

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]

    @property
    def appearance_resolved(self):
        """Preset configuration merged with this household's overrides."""
        return resolve_config(self.base_preset, self.appearance_overrides or {})

    @property
    def appearance_is_customised(self):
        return bool(self.appearance_overrides)


def bump_revision():
    Household.objects.filter(pk=1).update(revision=F('revision') + 1)


class DisplayDevice(models.Model):
    name = models.CharField(max_length=60, default='Living room')
    pairing_hash = models.CharField(max_length=64, unique=True, null=True)
    expires_at = models.DateTimeField()
    approved = models.BooleanField(default=False)
    revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class ActivityEntry(models.Model):
    actor = models.ForeignKey(Member, on_delete=models.PROTECT)
    message = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)


class AccessAttempt(models.Model):
    key = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WeatherSnapshot(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    payload = models.JSONField(default=dict)
    fetched_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
