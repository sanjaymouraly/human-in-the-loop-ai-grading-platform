from django import forms

class DatasetUploadForm(forms.Form):
    name = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    file = forms.FileField(help_text="CSV, JSON, or JSONL file. Max 10MB. See template.")
    format = forms.ChoiceField(choices=[('auto', 'Auto-detect'), ('csv', 'CSV'), ('json', 'JSON'), ('jsonl', 'JSONL')], initial='auto')

class DatasetPreviewForm(forms.Form):
    pass
