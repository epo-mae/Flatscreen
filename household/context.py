from .appearance import PRESETS, appearance_attrs, display_attrs, resolve_config, theme_color
from .models import Household
from shopping.known import CLASSIFICATION_ORDER
from shopping.models import ItemCategory

CATEGORY_CHOICES = [(key, ItemCategory(key).label) for key in CLASSIFICATION_ORDER]


def household_context(request):
    house = Household.objects.filter(pk=1).first()
    if house:
        config = house.appearance_resolved
    else:
        config = resolve_config('classic')
    return {'household': house, 'theme_color': theme_color(config),
            'appearance_attrs': appearance_attrs(config),
            'appearance_display_attrs': display_attrs(config),
            'appearance_presets': PRESETS,
            'shopping_categories': CATEGORY_CHOICES}