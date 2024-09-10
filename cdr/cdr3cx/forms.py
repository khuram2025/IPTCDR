from django import forms

from accounts.models import Extension
from .models import Quota

class QuotaForm(forms.ModelForm):
    class Meta:
        model = Quota
        fields = ['name', 'amount']



class AssignQuotaForm(forms.Form):
    quota = forms.ModelChoiceField(queryset=Quota.objects.none())
    extensions = forms.ModelMultipleChoiceField(
        queryset=Extension.objects.none(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2', 'style': 'width: 100%;'}),
        required=True
    )

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        if company:
            self.fields['quota'].queryset = Quota.objects.filter(company=company)
            extensions = Extension.objects.filter(company=company)
            self.fields['extensions'].queryset = extensions
            # print(f"Company: {company}")
            # print(f"Number of quotas: {self.fields['quota'].queryset.count()}")
            # print(f"Number of extensions: {extensions.count()}")
            # print(f"Extensions: {list(extensions.values_list('extension', flat=True))}")
        # else:
        #     print("No company provided to AssignQuotaForm")

        # Add Bootstrap classes to all fields
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})