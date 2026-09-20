"""Household-wide item-name and category memory shared by shopping and planning.

One shared shopping list sits underneath everywhere, so the learned names and
categories keep autocomplete, consistent spelling and Meal/Category grouping in
agreement across the shopping list and dinner ingredients.
"""
from .models import ItemCategory, KnownItem, ShoppingItem

# Canonical order used for the Category view and everywhere categories render.
CLASSIFICATION_ORDER = [
    ItemCategory.PRODUCE, ItemCategory.MEAT, ItemCategory.DAIRY, ItemCategory.BAKERY,
    ItemCategory.PANTRY, ItemCategory.FROZEN, ItemCategory.DRINKS, ItemCategory.HOUSEHOLD,
    ItemCategory.TOILETRIES, ItemCategory.OTHER,
]


def normalize_name(name):
    return ' '.join(str(name).split()).casefold()


def resolve_category(name, explicit=None):
    """The effective category for a name: an explicit pick wins, otherwise the
    household's remembered category, falling back to Other."""
    if explicit and explicit != ItemCategory.OTHER:
        return explicit
    known = KnownItem.objects.filter(normalized_name=normalize_name(name)).values_list('category', flat=True).first()
    if known:
        return known
    return ItemCategory.OTHER


def remember_item(name, category=None):
    """Learn a name spelling and (optionally) its category. The most common
    spelling becomes the canonical one shown in suggestions."""
    cleaned = ' '.join(str(name).split())
    normalized = normalize_name(cleaned)
    known, created = KnownItem.objects.get_or_create(
        normalized_name=normalized, defaults={'canonical_name': cleaned})
    spellings = dict(known.spellings)
    spellings[cleaned] = spellings.get(cleaned, 0) + 1
    known.spellings = spellings
    known.canonical_name = max(spellings, key=spellings.get)
    if not created:
        known.uses += 1
    if category and category != ItemCategory.OTHER:
        known.category = category
    known.save()
    return known


def known_suggestions(limit=12):
    return [
        {'name': known.canonical_name, 'category': known.category}
        for known in KnownItem.objects.order_by('-uses', '-last_used_at')[:limit]
    ]


def add_shopping_item(actor, *, name, quantity=1, note='', category=None, dinner_plan=None):
    """Add a shopping item, remembering its name/category.

    Merge policy: when the same unpurchased item already exists and belongs to
    the *same* dinner plan, their quantities merge. Otherwise a new row is kept
    so every item stays tied to the meal it came from (or is general).
    """
    cleaned = ' '.join(str(name).split())
    normalized = normalize_name(cleaned)
    if category is None:
        category = resolve_category(cleaned, None)

    merged = False
    existing = ShoppingItem.objects.filter(normalized_name=normalized, purchased=False, deleted_at=None).first()
    if existing and dinner_plan is not None and existing.dinner_plan_id == dinner_plan.pk:
        merged = True
        existing.quantity = min(999, existing.quantity + quantity)
        existing.version += 1
        existing.save(update_fields=['quantity', 'version'])
        item = existing
    else:
        item = ShoppingItem.objects.create(
            name=cleaned, normalized_name=normalized, quantity=quantity, note=note,
            category=category, dinner_plan=dinner_plan, added_by=actor)

    remember_item(cleaned, category)
    return item, merged