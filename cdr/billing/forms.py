from django import forms
from .models import CallRate, CallRecord
import random

class CallRateForm(forms.ModelForm):
    matching_criteria = forms.ChoiceField(choices=[], required=False, help_text="Comma separated list of matching criteria numbers")
    example_number = forms.CharField(max_length=20, required=False, help_text="Example number matching the criteria", widget=forms.TextInput(attrs={'readonly': 'readonly'}))

    class Meta:
        model = CallRate
        fields = ['call_type', 'rate_per_min', 'matching_criteria', 'example_number']

    def __init__(self, *args, **kwargs):
        super(CallRateForm, self).__init__(*args, **kwargs)
        unmatched_criteria = self.get_unmatched_criteria()
        self.fields['matching_criteria'].choices = [(criteria, criteria) for criteria in unmatched_criteria]
        if self.is_bound and self.data.get('matching_criteria'):
            self.fields['example_number'].initial = self.get_example_number(self.data.get('matching_criteria'))

    def get_unmatched_criteria(self):
        all_callees = CallRecord.objects.values_list('callee', flat=True).distinct()
        existing_criteria = set()
        for rate in CallRate.objects.all():
            existing_criteria.update(rate.matching_criteria.split(','))

        unmatched_criteria = set()
        for callee in all_callees:
            prefix = f"{callee[:2]}xxxxxxxx"
            if prefix not in existing_criteria:
                unmatched_criteria.add(prefix)

        return sorted(unmatched_criteria)

    def get_example_number(self, criteria):
        all_callees = CallRecord.objects.filter(callee__startswith=criteria[:2]).values_list('callee', flat=True)
        if all_callees:
            return random.choice(all_callees)
        return "No example available"
