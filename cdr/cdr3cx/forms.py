import json
import re

from django import forms
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from accounts.models import Extension
from .models import Quota, CallPattern
from .callpattern_presets import regex_from_stored


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

        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})


class CallPatternForm(forms.ModelForm):
    class Meta:
        model = CallPattern
        fields = ['name', 'pattern', 'call_type', 'rate_per_min', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'e.g. Saudi Mobile 05, Indonesia International',
                'id': 'id_name',
            }),
            'pattern': forms.TextInput(attrs={
                'class': 'form-control form-control-sm font-monospace',
                'placeholder': '05 or ^(0062|\\+62)\\d{9,12}',
                'id': 'id_pattern',
                'spellcheck': 'false',
            }),
            'call_type': forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_call_type'}),
            'rate_per_min': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'step': '0.01',
                'min': '0',
                'id': 'id_rate_per_min',
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Optional note for your team',
                'id': 'id_description',
            }),
        }
        labels = {
            'name': 'Rule name',
            'pattern': 'Match pattern',
            'call_type': 'Call type',
            'rate_per_min': 'Rate per minute (SAR)',
            'description': 'Description',
        }

    def clean_pattern(self):
        pattern = (self.cleaned_data.get('pattern') or '').strip()
        if not pattern:
            raise forms.ValidationError('Pattern is required.')
        try:
            re.compile(CallPattern(pattern=pattern).get_regex_pattern())
        except re.error as exc:
            raise forms.ValidationError(f'Invalid pattern: {exc}') from exc
        return pattern

    def clean_rate_per_min(self):
        rate = self.cleaned_data.get('rate_per_min')
        if rate is not None and rate < 0:
            raise forms.ValidationError('Rate cannot be negative.')
        return rate
