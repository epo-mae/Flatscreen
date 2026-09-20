import re
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .appearance import FONT_STACKS
from .models import Household, Member
from .weather import WeatherServiceError, find_location


HEX_COLOUR = re.compile(r'^#[0-9a-fA-F]{6}$')

FONT_CHOICES = [(key, label) for key, label in [
    ('humanist', 'Humanist'), ('system', 'System'),
    ('rounded', 'Rounded'), ('serif', 'Serif'),
    ('display-serif', 'Display serif'), ('monospace', 'Monospace')]]
WIDTH_CHOICES = [('narrow', 'Narrow'), ('standard', 'Standard'), ('wide', 'Wide'), ('full', 'Full')]
DENSITY_CHOICES = [('compact', 'Compact'), ('standard', 'Standard'), ('spacious', 'Spacious')]
HEADER_CHOICES = [('compact', 'Compact'), ('standard', 'Standard'), ('prominent', 'Prominent')]
RADIUS_CHOICES = [('small', 'Small'), ('standard', 'Standard'), ('large', 'Large'), ('xlarge', 'Extra large')]
SHADOW_CHOICES = [('none', 'None'), ('soft', 'Soft'), ('medium', 'Medium'), ('strong', 'Strong')]
BUTTON_CHOICES = [('filled', 'Filled'), ('pill', 'Pill'), ('outlined', 'Outlined'), ('flat', 'Flat'), ('square', 'Square')]
INPUT_CHOICES = [('outlined', 'Outlined'), ('underline', 'Underline'), ('filled', 'Filled')]
CARD_CHOICES = [('flat', 'Flat'), ('elevated', 'Elevated'), ('bordered', 'Bordered'), ('minimal', 'Minimal')]
STATUS_CHOICES = [('labels', 'Labels'), ('pills', 'Pills'), ('dots', 'Dots')]
LIST_CHOICES = [('separated', 'Separated'), ('roomy', 'Roomy'), ('compact', 'Compact')]
DASHBOARD_CHOICES = [('grid', 'Grid'), ('sections', 'Sections'), ('cards', 'Cards'), ('editorial', 'Editorial')]
GUTTER_CHOICES = [('compact', 'Compact'), ('standard', 'Standard'), ('large', 'Large')]
CLOCK_CHOICES = [('small', 'Small'), ('standard', 'Standard'), ('large', 'Large')]
DISPLAY_TYPE_CHOICES = [('compact', 'Compact'), ('standard', 'Standard'), ('large', 'Large')]


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


def _field(kind, label, **attrs):
    base = {'label': label}
    base.update(attrs)
    return kind, base


APPEARANCE_SPECS = [
    _field(forms.ChoiceField, 'Body font', choices=FONT_CHOICES),
    _field(forms.ChoiceField, 'Heading font', choices=FONT_CHOICES),
    _field(forms.IntegerField, 'Base text size', min_value=14, max_value=20, widget=forms.NumberInput(attrs={'min': 14, 'max': 20})),
    _field(forms.IntegerField, 'Body weight', min_value=100, max_value=900, widget=forms.NumberInput(attrs={'min': 100, 'max': 900, 'step': 100})),
    _field(forms.IntegerField, 'Heading weight', min_value=100, max_value=900, widget=forms.NumberInput(attrs={'min': 100, 'max': 900, 'step': 100})),
    _field(forms.DecimalField, 'Body line height', min_value=1.2, max_value=2.0, decimal_places=2, widget=forms.NumberInput(attrs={'min': 1.2, 'max': 2.0, 'step': 0.05})),
    _field(forms.DecimalField, 'Heading line height', min_value=1.0, max_value=1.8, decimal_places=2, widget=forms.NumberInput(attrs={'min': 1.0, 'max': 1.8, 'step': 0.05})),
    _field(forms.DecimalField, 'Body letter spacing', min_value=-0.02, max_value=0.02, decimal_places=3, widget=forms.NumberInput(attrs={'min': -0.02, 'max': 0.02, 'step': 0.005})),
    _field(forms.DecimalField, 'Heading letter spacing', min_value=-0.05, max_value=0.0, decimal_places=3, widget=forms.NumberInput(attrs={'min': -0.05, 'max': 0.0, 'step': 0.005})),
    _field(forms.CharField, 'Background', widget=forms.ColorInput),
    _field(forms.CharField, 'Card surface', widget=forms.ColorInput),
    _field(forms.CharField, 'Secondary surface', widget=forms.ColorInput),
    _field(forms.CharField, 'Accent', widget=forms.ColorInput),
    _field(forms.CharField, 'Text', widget=forms.ColorInput),
    _field(forms.CharField, 'Muted text', widget=forms.ColorInput),
    _field(forms.CharField, 'Border', widget=forms.ColorInput),
    _field(forms.ChoiceField, 'Corner radius', choices=RADIUS_CHOICES),
    _field(forms.ChoiceField, 'Shadows', choices=SHADOW_CHOICES),
    _field(forms.ChoiceField, 'Button style', choices=BUTTON_CHOICES),
    _field(forms.ChoiceField, 'Input style', choices=INPUT_CHOICES),
    _field(forms.ChoiceField, 'Card style', choices=CARD_CHOICES),
    _field(forms.ChoiceField, 'Status style', choices=STATUS_CHOICES),
    _field(forms.ChoiceField, 'List style', choices=LIST_CHOICES),
    _field(forms.ChoiceField, 'Content width', choices=WIDTH_CHOICES),
    _field(forms.ChoiceField, 'Density', choices=DENSITY_CHOICES),
    _field(forms.ChoiceField, 'Page header', choices=HEADER_CHOICES),
    _field(forms.ChoiceField, 'Dashboard style', choices=DASHBOARD_CHOICES),
    _field(forms.IntegerField, 'Dashboard columns', min_value=1, max_value=4, widget=forms.NumberInput(attrs={'min': 1, 'max': 4})),
    _field(forms.ChoiceField, 'Dashboard gutter', choices=GUTTER_CHOICES),
    _field(forms.ChoiceField, 'Wall density', choices=[('standard', 'Standard'), ('spacious', 'Spacious'), ('dense', 'Dense')]),
    _field(forms.IntegerField, 'Wall columns', min_value=2, max_value=3, widget=forms.NumberInput(attrs={'min': 2, 'max': 3})),
    _field(forms.ChoiceField, 'Clock size', choices=CLOCK_CHOICES),
    _field(forms.ChoiceField, 'Wall text', choices=DISPLAY_TYPE_CHOICES),
]

SECTION_FIELDS = [
    ('typography', ['body_font', 'heading_font', 'base_size', 'body_weight', 'heading_weight', 'body_line_height', 'heading_line_height', 'body_tracking', 'heading_tracking']),
    ('colour', ['background', 'surface', 'wash', 'accent', 'text', 'muted', 'border']),
    ('geometry', ['radius', 'shadow']),
    ('components', ['button', 'input', 'card', 'status', 'list']),
    ('layout', ['content_width', 'density', 'page_header']),
    ('dashboard', ['style', 'cols', 'gutter']),
    ('display', ['density', 'cols', 'clock', 'type']),
]

FIELD_NAMES = ([(section, field) for section, fields in SECTION_FIELDS for field in fields])
FIELD_NAME = {f'{section}_{field}': (section, field) for section, field in FIELD_NAMES}


class AppearanceForm(forms.Form):
    """Grouped design-system controls. Values map onto preset configuration."""

    def __init__(self, *args, config=None, **kwargs):
        super().__init__(*args, **kwargs)
        for index, (section, field) in enumerate(FIELD_NAMES):
            kind, base = APPEARANCE_SPECS[index]
            base.setdefault('required', False)
            self.fields[f'{section}_{field}'] = kind(**base)
        if config:
            for index, (section, field) in enumerate(FIELD_NAMES):
                key = f'{section}_{field}'
                value = config.get(section, {}).get(field)
                if value is not None:
                    self.fields[key].initial = value

    def clean(self):
        cleaned = super().clean()
        for name in (f'colour_{field}' for field in ('background', 'surface', 'wash', 'accent', 'text', 'muted', 'border')):
            value = cleaned.get(name)
            if value and not HEX_COLOUR.match(value):
                self.add_error(name, 'Use a six-digit hex colour like #bd633b.')
        return cleaned

    def cleaned_overrides(self):
        """Values entered for the stock preset, as sparse dotted-key overrides."""
        overrides = {}
        for name, value in self.cleaned_data.items():
            if value is None or value == '':
                continue
            if isinstance(value, Decimal) and value == value.to_integral_value():
                value = int(value)
            section, field = FIELD_NAME[name]
            overrides[f'{section}.{field}'] = value
        return overrides
