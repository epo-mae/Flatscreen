from django import forms
from household.models import Member
from .models import CalendarEvent, Chore, DinnerPlan, HouseNotice


class DinnerPlanForm(forms.ModelForm):
    class Meta:
        model = DinnerPlan
        fields = ['date', 'cook', 'meal', 'serving_time', 'notes', 'is_happening']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'serving_time': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.TextInput(attrs={'placeholder': 'Anything the household should know'}),
        }
        labels = {'is_happening': 'Dinner is happening'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cook'].queryset = Member.objects.filter(is_active=True).order_by('display_name', 'username')
        self.fields['cook'].required = False


class CalendarEventForm(forms.ModelForm):
    class Meta:
        model = CalendarEvent
        fields = ['title', 'event_date', 'start_time', 'end_time', 'category', 'description']
        widgets = {
            'event_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.TextInput(attrs={'placeholder': 'Optional details'}),
        }


class HouseNoticeForm(forms.ModelForm):
    expires_in = forms.ChoiceField(choices=[
        ('24', 'After 24 hours'), ('72', 'After 3 days'), ('168', 'After 1 week'), ('', 'No automatic expiry'),
    ], required=False, initial='72')

    class Meta:
        model = HouseNotice
        fields = ['title', 'message', 'importance']
        widgets = {'message': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Keep it useful and concise'})}


class ChoreForm(forms.ModelForm):
    class Meta:
        model = Chore
        fields = ['title', 'assigned_to', 'due_date', 'repeat', 'notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.TextInput(attrs={'placeholder': 'Optional instructions'}),
        }
        labels = {'assigned_to': 'Responsible person'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = Member.objects.filter(is_active=True).order_by('display_name', 'username')
        self.fields['assigned_to'].required = False
