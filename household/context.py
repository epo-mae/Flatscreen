from .models import Household


def household_context(request):
    return {'household': Household.objects.filter(pk=1).first()}

