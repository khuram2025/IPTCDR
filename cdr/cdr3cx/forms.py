from django import forms

from accounts.models import Extension
from .models import Quota

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

