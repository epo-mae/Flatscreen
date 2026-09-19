import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .appearance import APPEARANCE_FIELDS, PRESETS
from .models import Household, Member
from .weather import WeatherServiceError, find_location


HEX_COLOUR = re.compile(r'^#[0-9a-fA-F]{6}$')


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


class AppearanceForm(forms.Form):
    """Fine-tuning controls for the selected appearance preset."""

    background = forms.CharField(widget=forms.ColorInput, label='Background')
    surface = forms.CharField(widget=forms.ColorInput, label='Card surface')
    wash = forms.CharField(widget=forms.ColorInput, label='Secondary surface')
    accent = forms.CharField(widget=forms.ColorInput, label='Accent')
    text = forms.CharField(widget=forms.ColorInput, label='Text')
    muted = forms.CharField(widget=forms.ColorInput, label='Muted text')
    border = forms.CharField(widget=forms.ColorInput, label='Border')
    radius = forms.IntegerField(min_value=0, max_value=24, widget=forms.NumberInput(attrs={'min': 0, 'max': 24, 'type': 'number'}), label='Corner radius')
    font_scale = forms.IntegerField(min_value=80, max_value=130, widget=forms.NumberInput(attrs={'min': 80, 'max': 130, 'type': 'number'}), label='Text size (%)')
    shadow = forms.TypedChoiceField(coerce=int, choices=[(0, 'None'), (1, 'Soft'), (2, 'Strong')], label='Shadows')
    spacing = forms.IntegerField(min_value=85, max_value=125, widget=forms.NumberInput(attrs={'min': 85, 'max': 125, 'type': 'number'}), label='Spacing (%)')

    def clean(self):
        cleaned = super().clean()
        for field in ('background', 'surface', 'wash', 'accent', 'text', 'muted', 'border'):
            value = cleaned.get(field)
            if value is not None and not HEX_COLOUR.match(value):
                self.add_error(field, 'Use a six-digit hex colour like #bd633b.')
        return cleaned

    def cleaned_values(self):
        return {field: self.cleaned_data[field] for field in APPEARANCE_FIELDS}
