from django.conf import settings
from django.db import models


class ItemCategory(models.TextChoices):
    PRODUCE = 'produce', 'Produce'
    MEAT = 'meat', 'Meat'
    DAIRY = 'dairy', 'Dairy'
    BAKERY = 'bakery', 'Bakery'
    PANTRY = 'pantry', 'Pantry'
    FROZEN = 'frozen', 'Frozen'
    DRINKS = 'drinks', 'Drinks'
    HOUSEHOLD = 'household', 'Household'
    TOILETRIES = 'toiletries', 'Toiletries'
    OTHER = 'other', 'Other'


class ShoppingItem(models.Model):
    name = models.CharField(max_length=100)
    normalized_name = models.CharField(max_length=100, db_index=True)
    quantity = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=240, blank=True)
    category = models.CharField(max_length=20, choices=ItemCategory.choices, default=ItemCategory.OTHER)
    dinner_plan = models.ForeignKey('planning.DinnerPlan', on_delete=models.SET_NULL, null=True, blank=True, related_name='shopping_items')
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='added_items')
    added_at = models.DateTimeField(auto_now_add=True)
    purchased = models.BooleanField(default=False)
    purchased_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='purchased_items')
    purchased_at = models.DateTimeField(null=True)
    deleted_at = models.DateTimeField(null=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gte=1, quantity__lte=999), name='shopping_quantity_range')]


class KnownItem(models.Model):
    """The household's learned item memory: preferred spelling and category.

    Kept from manually added items and dinner ingredients, so autocomplete,
    consistent naming and category grouping agree across the whole app.
    """
    normalized_name = models.CharField(max_length=100, unique=True, db_index=True)
    canonical_name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=ItemCategory.choices, default=ItemCategory.OTHER)
    uses = models.PositiveIntegerField(default=1)
    spellings = models.JSONField(default=dict)
    last_used_at = models.DateTimeField(auto_now=True)


class Mutation(models.Model):
    operation_id = models.UUIDField(unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    response = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

