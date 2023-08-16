from django import forms
from .models import PreferenceChoice, IssueCategory, IssueSeverity, VerificationStatus

class AssignmentCreateForm(forms.Form):
    dataset_id = forms.IntegerField()
    reviewer_usernames = forms.CharField(
        help_text="Comma-separated usernames",
        widget=forms.Textarea(attrs={'rows': 2})
    )
    assign_all = forms.BooleanField(required=False, initial=False, help_text="Assign all items in dataset")

    task_ids = forms.CharField(
        required=False,
        help_text="Optional: comma-separated task_ids to assign (if not assign_all)",
        widget=forms.Textarea(attrs={'rows': 2})
    )

class ReviewForm(forms.Form):
    # Dynamic fields will be added in view
    preference = forms.ChoiceField(choices=PreferenceChoice.choices, widget=forms.RadioSelect)
    confidence = forms.IntegerField(min_value=1, max_value=5, initial=3)
    rationale = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=True, help_text="Explain your preference")

    def __init__(self, *args, rubric=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rubric = rubric
        if rubric:
            for dim in rubric.dimensions.order_by('order'):
                # Score for A and B
                self.fields[f'dim_{dim.id}_a'] = forms.IntegerField(
                    required=not dim.allow_na,
                    min_value=dim.scale_min,
                    max_value=dim.scale_max,
                    label=f"{dim.name} - Response A",
                    help_text=dim.description,
                    widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:100px'})
                )
                self.fields[f'dim_{dim.id}_b'] = forms.IntegerField(
                    required=not dim.allow_na,
                    min_value=dim.scale_min,
                    max_value=dim.scale_max,
                    label=f"{dim.name} - Response B",
                    widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:100px'})
                )
                if dim.allow_na:
                    self.fields[f'dim_{dim.id}_na'] = forms.BooleanField(required=False, label="N/A")

class IssueForm(forms.Form):
    response_target = forms.ChoiceField(choices=[('response_a', 'Response A (original)'), ('response_b', 'Response B (original)')])
    category = forms.ChoiceField(choices=IssueCategory.choices)
    severity = forms.ChoiceField(choices=IssueSeverity.choices, initial=IssueSeverity.MEDIUM)
    excerpt = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    evidence = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False, help_text="Source or evidence")
    explanation = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=True)
    correction = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)

class AdjudicationForm(forms.Form):
    final_preference = forms.ChoiceField(choices=PreferenceChoice.choices, widget=forms.RadioSelect)
    rationale = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=True)
