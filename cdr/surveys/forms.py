from django import forms
from django.forms import inlineformset_factory

from surveys.models import SurveyCampaign, SurveyQuestion


class SurveyCampaignForm(forms.ModelForm):
    class Meta:
        model = SurveyCampaign
        fields = [
            'name', 'cfd_app_name', 'license_verified', 'license_note',
            'match_window_minutes', 'csat_target_pct', 'is_active',
            'intro_audio_url', 'goodbye_audio_url',
        ]
        widgets = {
            'license_note': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'cfd_app_name': forms.TextInput(attrs={'class': 'form-control'}),
            'match_window_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'csat_target_pct': forms.NumberInput(attrs={'class': 'form-control'}),
            'intro_audio_url': forms.URLInput(attrs={'class': 'form-control'}),
            'goodbye_audio_url': forms.URLInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['license_verified'].widget.attrs['class'] = 'form-check-input'
        self.fields['is_active'].widget.attrs['class'] = 'form-check-input'


class SurveyQuestionForm(forms.ModelForm):
    class Meta:
        model = SurveyQuestion
        fields = ['order', 'tag', 'question_type', 'prompt_text', 'min_value', 'max_value', 'required']
        widgets = {
            'order': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'tag': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'question_type': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'prompt_text': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
            'min_value': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'max_value': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['required'].widget.attrs['class'] = 'form-check-input'


SurveyQuestionFormSet = inlineformset_factory(
    SurveyCampaign, SurveyQuestion, form=SurveyQuestionForm,
    extra=1, can_delete=True,
)


class CompanySurveyFlagsForm(forms.Form):
    survey_enabled = forms.BooleanField(required=False, label='Enable surveys for this tenant')
    survey_cfd_verified = forms.BooleanField(
        required=False,
        label='3CX Call Flow Designer / Call Flow Apps license confirmed',
    )
