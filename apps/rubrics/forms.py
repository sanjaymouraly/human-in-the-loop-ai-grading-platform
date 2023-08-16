from django import forms
from .models import Rubric, RubricDimension
import json

class RubricForm(forms.ModelForm):
    class Meta:
        model = Rubric
        fields = ['name', 'description', 'instructions']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'instructions': forms.Textarea(attrs={'rows': 4}),
        }

class RubricDimensionForm(forms.ModelForm):
    anchored_descriptions_text = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'JSON like {"1": "Poor", "5": "Excellent"}'}),
        required=False,
        help_text="JSON mapping score -> description"
    )

    class Meta:
        model = RubricDimension
        fields = ['key', 'name', 'description', 'scale_min', 'scale_max', 'allow_na', 'weight', 'order', 'is_required']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.anchored_descriptions:
            self.fields['anchored_descriptions_text'].initial = json.dumps(self.instance.anchored_descriptions, indent=2)

    def clean_anchored_descriptions_text(self):
        text = self.cleaned_data.get('anchored_descriptions_text', '').strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                raise forms.ValidationError("Must be a JSON object")
            return data
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f"Invalid JSON: {e}")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.anchored_descriptions = self.cleaned_data.get('anchored_descriptions_text', {})
        if commit:
            instance.save()
        return instance

class RubricDimensionFormSet(forms.BaseInlineFormSet):
    pass
