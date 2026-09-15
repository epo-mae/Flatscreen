from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class DinnerPlan(models.Model):
    date = models.DateField(unique=True)
    cook = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='dinner_plans')
    meal = models.CharField(max_length=120, blank=True)
    notes = models.CharField(max_length=240, blank=True)
    is_happening = models.BooleanField(default=True)
    serving_time = models.TimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_dinner_plans')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='updated_dinner_plans')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date']


class CalendarEvent(models.Model):
    class Category(models.TextChoices):
        HOUSEHOLD = 'household', 'Household'
        VISITOR = 'visitor', 'Visitors'
        MAINTENANCE = 'maintenance', 'Maintenance'
        MONEY = 'money', 'Rent and bills'
        CELEBRATION = 'celebration', 'Celebration'
        OTHER = 'other', 'Other'

    title = models.CharField(max_length=120)
    event_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    description = models.CharField(max_length=300, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.HOUSEHOLD)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='calendar_events')
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['event_date', 'start_time', 'id']
        indexes = [models.Index(fields=['event_date', 'deleted_at'])]

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'End time must be later than the start time.'})


class HouseNotice(models.Model):
    class Importance(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        IMPORTANT = 'important', 'Important'

    title = models.CharField(max_length=100)
    message = models.CharField(max_length=300)
    importance = models.CharField(max_length=10, choices=Importance.choices, default=Importance.NORMAL)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='house_notices')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['expires_at', 'deleted_at'])]


class Chore(models.Model):
    class Repeat(models.TextChoices):
        ONCE = 'once', 'One time'
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        FORTNIGHTLY = 'fortnightly', 'Every 2 weeks'
        MONTHLY = 'monthly', 'Monthly'

    title = models.CharField(max_length=100)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='assigned_chores')
    due_date = models.DateField()
    repeat = models.CharField(max_length=20, choices=Repeat.choices, default=Repeat.ONCE)
    notes = models.CharField(max_length=240, blank=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_chores')
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='completed_chores')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['completed_at', 'due_date', 'id']
        indexes = [models.Index(fields=['due_date', 'completed_at', 'deleted_at'])]


class ChoreCompletion(models.Model):
    chore = models.ForeignKey(Chore, on_delete=models.CASCADE, related_name='completions')
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='chore_completion_history')
    completed_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField()

    class Meta:
        ordering = ['-completed_at']
