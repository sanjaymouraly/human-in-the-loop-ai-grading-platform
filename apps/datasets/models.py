from django.db import models
from django.contrib.auth.models import User
import hashlib
import json

class Dataset(models.Model):
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='datasets')
    name = models.CharField(max_length=200)
    version = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('project', 'name', 'version')

    def __str__(self):
        return f"{self.name} v{self.version} ({self.project.name})"

class DatasetItem(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='items')
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='dataset_items')
    task_id = models.CharField(max_length=200, db_index=True)
    prompt = models.TextField()
    context = models.TextField(blank=True)
    response_a = models.TextField()
    response_b = models.TextField()
    model_a = models.CharField(max_length=100, blank=True)
    model_b = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    reference_answer = models.TextField(blank=True)
    order_index = models.PositiveIntegerField(default=0)
    content_hash = models.CharField(max_length=64, db_index=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order_index', 'created_at']
        unique_together = ('dataset', 'task_id')
        indexes = [
            models.Index(fields=['project', 'task_id']),
        ]

    def __str__(self):
        return f"{self.task_id} - {self.prompt[:50]}"

    def save(self, *args, **kwargs):
        if not self.content_hash:
            # Compute hash for duplicate detection
            content = f"{self.prompt}|{self.response_a}|{self.response_b}"
            self.content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        super().save(*args, **kwargs)

    def get_responses_for_display(self, display_a_is_original_a: bool):
        """Return tuple (display_a, display_b, model_display_a, model_display_b) respecting randomization"""
        if display_a_is_original_a:
            return self.response_a, self.response_b, self.model_a, self.model_b
        else:
            return self.response_b, self.response_a, self.model_b, self.model_a

    def get_original_label_for_display(self, display_choice: str, display_a_is_original_a: bool):
        """
        Convert reviewer's display choice (A/B) back to original label.
        display_choice: 'response_a', 'response_b', 'tie', 'both_bad'
        Returns original preference.
        """
        if display_choice in ('tie', 'both_bad'):
            return display_choice
        if display_choice == 'response_a':
            return 'response_a' if display_a_is_original_a else 'response_b'
        if display_choice == 'response_b':
            return 'response_b' if display_a_is_original_a else 'response_a'
        return display_choice
