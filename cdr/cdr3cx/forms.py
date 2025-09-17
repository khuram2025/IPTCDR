from django import forms

from accounts.models import Extension
from .models import Quota, CallPattern

class QuotaForm(forms.ModelForm):
    class Meta:
        model = Quota
        fields = ['name', 'amount']



class AssignQuotaForm(forms.Form):
    quota = forms.ModelChoiceField(
        queryset=Quota.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    extensions = forms.ModelMultipleChoiceField(
        queryset=Extension.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        if company:
            self.fields['quota'].queryset = Quota.objects.filter(company=company)
            self.fields['extensions'].queryset = Extension.objects.filter(company=company)

        # Add Bootstrap classes to all fields
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})


class CallPatternForm(forms.ModelForm):
    class Meta:
        model = CallPattern
        fields = ['name', 'pattern', 'call_type', 'rate_per_min', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., US International, Saudi Mobile'}),
            'pattern': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., +1, 059'}),
            'call_type': forms.Select(attrs={'class': 'form-control'}),
            'rate_per_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional description'}),
        }
        labels = {
            'name': 'Rule Name',
            'pattern': 'Pattern',
            'call_type': 'Call Type',
            'rate_per_min': 'Rate per Minute (SAR)',
            'description': 'Description'
        }
        help_texts = {
            'name': 'Enter a descriptive name for this calling rule',
            'pattern': 'Enter the pattern to match phone numbers (e.g., +1 for US, 059 for Saudi mobile)',
            'rate_per_min': 'Enter the rate in Saudi Riyals per minute'
        }

