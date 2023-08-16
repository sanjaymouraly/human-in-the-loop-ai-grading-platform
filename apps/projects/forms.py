from django import forms
from .models import Project, MembershipRole

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'instructions', 'task_type', 'goal', 'status', 'blind_review', 'require_double_review', 'balance_ab_order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'instructions': forms.Textarea(attrs={'rows': 4}),
            'goal': forms.Textarea(attrs={'rows': 3}),
        }

class MembershipForm(forms.Form):
    username = forms.CharField(max_length=150, help_text="Existing username")
    role = forms.ChoiceField(choices=MembershipRole.choices, initial=MembershipRole.REVIEWER)
