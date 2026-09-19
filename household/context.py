from .appearance import classic_defaults
from .models import Household


def household_context(request):
    house = Household.objects.filter(pk=1).first()
    background = house.appearance_settings['background'] if house else classic_defaults()['background']
    return {'household': house, 'theme_color': background}

