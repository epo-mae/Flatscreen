from django.conf import settings
from django.db import models


class ShoppingItem(models.Model):
    name = models.CharField(max_length=100)
    normalized_name = models.CharField(max_length=100, db_index=True)
    quantity = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=240, blank=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='added_items')
    added_at = models.DateTimeField(auto_now_add=True)
    purchased = models.BooleanField(default=False)
    purchased_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='purchased_items')
    purchased_at = models.DateTimeField(null=True)
    deleted_at = models.DateTimeField(null=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gte=1, quantity__lte=999), name='shopping_quantity_range')]


class Mutation(models.Model):
    operation_id = models.UUIDField(unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    response = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

