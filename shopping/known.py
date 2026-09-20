"""Household-wide item-name and category memory shared by shopping and planning.

One shared shopping list sits underneath everywhere, so the learned names and
categories keep autocomplete, consistent spelling and Meal/Category grouping in
agreement across the shopping list and dinner ingredients.
"""
import re

from .models import ItemCategory, KnownItem, ShoppingItem

# Canonical order used for the Category view and everywhere categories render.
CLASSIFICATION_ORDER = [
    ItemCategory.PRODUCE, ItemCategory.MEAT, ItemCategory.DAIRY, ItemCategory.BAKERY,
    ItemCategory.PANTRY, ItemCategory.FROZEN, ItemCategory.DRINKS, ItemCategory.HOUSEHOLD,
    ItemCategory.TOILETRIES, ItemCategory.OTHER,
]

# Built-in keyword rules. Add words to the most natural category; longer
# keywords are tried first, so a phrase like "canned tomatoes" (Pantry) beats
# the single word "tomato" (Produce). Matching is case-insensitive and tolerates
# plurals ("sauces", "frozen peas"), so plurals do not need their own entries,
# but add any phrasing that should out-rank a shorter match.
KEYWORD_RULES = {
    ItemCategory.PANTRY: ('canned tomato', 'tinned tomato', 'tomato paste', 'pasta',
                          'rice', 'flour', 'sugar', 'tortilla', 'noodles', 'oats',
                          'cereal', 'beans', 'lentil', 'chickpea', 'stock', 'broth',
                          'olive oil', 'vinegar', 'curry paste', 'sauce'),
    ItemCategory.FROZEN: ('ice cream', 'frozen'),
    ItemCategory.BAKERY: ('bread', 'bun', 'bagel', 'croissant', 'muffin', 'baguette',
                          'pita', 'naan', 'scone', 'pastry', 'roll', 'loaf'),
    ItemCategory.MEAT: ('chicken', 'beef', 'mince', 'bacon', 'sausage', 'steak',
                        'lamb', 'ham', 'salami', 'turkey', 'pork', 'meatball'),
    ItemCategory.DAIRY: ('cream cheese', 'sour cream', 'cheese', 'butter', 'milk',
                         'yoghurt', 'yogurt', 'cream', 'feta', 'mozzarella'),
    ItemCategory.PRODUCE: ('tomato', 'lettuce', 'onion', 'potato', 'apple', 'banana',
                           'carrot', 'broccoli', 'cucumber', 'pepper', 'avocado',
                           'garlic', 'ginger', 'spinach', 'beetroot', 'cabbage',
                           'cauliflower', 'celery', 'zucchini', 'mushroom',
                           'pineapple', 'orange', 'lemon', 'lime', 'grape',
                           'strawberry', 'blueberry', 'mango', 'kiwi', 'melon',
                           'peach', 'pear', 'plum', 'corn', 'peas', 'salad',
                           'berries', 'herbs'),
    ItemCategory.DRINKS: ('juice', 'soda', 'water', 'tea', 'coffee', 'milk tea'),
    ItemCategory.HOUSEHOLD: ('dishwashing', 'dish soap', 'washing powder', 'laundry',
                             'rubbish bag', 'bin bag', 'kitchen roll', 'cleaning',
                             'detergent'),
    ItemCategory.TOILETRIES: ('shampoo', 'toothpaste', 'toothbrush', 'soap',
                              'deodorant', 'razor', 'moisturiser', 'moisturizer',
                              'conditioner', 'body wash', 'face wash'),
}

_MATCHERS = sorted(
    (
        (keyword, category, re.compile(
            r'\b' + r'\s+'.join(re.escape(token) for token in keyword.split()[:-1]) + (
                r'\s+' if ' ' in keyword else '') + re.escape(keyword.split()[-1]) + r'(?:s|es)?\b'))
        for category, keywords in KEYWORD_RULES.items()
        for keyword in keywords
    ),
    key=lambda entry: len(entry[0]),
    reverse=True,
)


def normalize_name(name):
    return ' '.join(str(name).split()).casefold()


def keyword_category(normalized):
    """The category a normalized name matches under the built-in rules, else None."""
    for _, category, pattern in _MATCHERS:
        if pattern.search(normalized):
            return category
    return None


def resolve_category(name, explicit=None):
    """The effective category for a name.

    An explicit pick always wins (including Other), otherwise the household's
    remembered category for the exact item is used, then the built-in keyword
    rules, falling back to Other.
    """
    if explicit:
        return explicit
    normalized = normalize_name(name)
    known = KnownItem.objects.filter(normalized_name=normalized).values_list('category', flat=True).first()
    if known:
        return known
    return keyword_category(normalized) or ItemCategory.OTHER


def remember_item(name, category=None):
    """Learn a name spelling and (optionally) its category. The most common
    spelling becomes the canonical one shown in suggestions. Only pass a
    category for a deliberate correction; automatically guessed categories are
    never stored."""
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
    if category:
        known.category = category
    known.save()
    return known


def known_suggestions(limit=12):
    return [
        {'name': known.canonical_name, 'category': known.category}
        for known in KnownItem.objects.order_by('-uses', '-last_used_at')[:limit]
    ]


def add_shopping_item(actor, *, name, quantity=1, note='', category=None, dinner_plan=None):
    """Add a shopping item. The effective category comes from a passed category
    (a deliberate pick) or an automatic guess; only deliberate picks are
    remembered for the future.

    Merge policy: when the same unpurchased item already exists and belongs to
    the *same* dinner plan, their quantities merge. Otherwise a new row is kept
    so every item stays tied to the meal it came from (or is general).
    """
    cleaned = ' '.join(str(name).split())
    normalized = normalize_name(cleaned)
    explicit = bool(category)
    if not category:
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

    remember_item(cleaned, category if explicit else None)
    return item, merged