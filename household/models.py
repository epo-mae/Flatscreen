from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F

from .appearance import APPEARANCE_FIELDS, PRESET_CHOICES, PRESETS, classic_defaults, preset_values


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
    appearance_preset = models.CharField(max_length=24, choices=PRESET_CHOICES, default='classic')
    appearance_values = models.JSONField(default=classic_defaults)
    revision = models.PositiveBigIntegerField(default=1)

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]

    @property
    def appearance_settings(self):
        """Authoritative values: stored values win, preset fills any gaps."""
        base = preset_values(self.appearance_preset)
        stored = self.appearance_values or {}
        for field in APPEARANCE_FIELDS:
            value = stored.get(field)
            if value is not None:
                base[field] = value
        return base

    @property
    def appearance_is_customised(self):
        if self.appearance_preset not in PRESETS:
            return False
        for field, stock in PRESETS[self.appearance_preset]['values'].items():
            if self.appearance_values.get(field) != stock:
                return True
        return False


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
