from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Household, Member
from .weather import WeatherServiceError, find_location


class HouseholdForm(forms.ModelForm):
    class Meta:
        model = Household
        fields = ['name', 'timezone']

    def clean_timezone(self):
        value = self.cleaned_data['timezone']
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise forms.ValidationError('Use a valid timezone, for example Pacific/Auckland.')
        return value


class WeatherLocationForm(forms.Form):
    location = forms.CharField(max_length=100, label='Town or city', help_text='For example: Auckland, Wellington, or Christchurch')

    def clean_location(self):
        value = ' '.join(self.cleaned_data['location'].split())
        try:
            self.match = find_location(value)
        except WeatherServiceError as exc:
            raise forms.ValidationError(str(exc))
        return value


class MemberForm(UserCreationForm):
    class Meta:
        model = Member
        fields = ['username', 'display_name', 'role', 'password1', 'password2']


class DisplayNameForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ['display_name']
        labels = {'display_name': 'Display name'}
        help_texts = {'display_name': 'Shown to the household instead of your username.'}
