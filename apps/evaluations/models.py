from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import random

class AssignmentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    SUBMITTED = 'submitted', 'Submitted'
    SKIPPED = 'skipped', 'Skipped'

class PreferenceChoice(models.TextChoices):
    RESPONSE_A = 'response_a', 'Response A'
    RESPONSE_B = 'response_b', 'Response B'
    TIE = 'tie', 'Tie'
    BOTH_BAD = 'both_bad', 'Both Unacceptable'

    @classmethod
    def display_labels(cls):
        return {
            cls.RESPONSE_A: 'Response A is better',
            cls.RESPONSE_B: 'Response B is better',
            cls.TIE: 'Tie - equally good',
            cls.BOTH_BAD: 'Both unacceptable',
        }

class IssueCategory(models.TextChoices):
    HALLUCINATION = 'hallucination', 'Hallucinated Facts'
    INCORRECT_CALC = 'incorrect_calc', 'Incorrect Calculation'
    UNSUPPORTED_CLAIM = 'unsupported_claim', 'Unsupported Claim'
    MISSED_CONSTRAINT = 'missed_constraint', 'Missed Constraint'
    FORMATTING = 'formatting', 'Incorrect Formatting'
    OMITTED_REQ = 'omitted_req', 'Omitted Requirement'
    BROKEN_CODE = 'broken_code', 'Broken Code'
    REASONING_MISTAKE = 'reasoning_mistake', 'Reasoning Mistake'
    UNSAFE_CONTENT = 'unsafe_content', 'Unsafe Content'
    OTHER = 'other', 'Other'

class IssueSeverity(models.TextChoices):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    CRITICAL = 'critical', 'Critical'

class VerificationStatus(models.TextChoices):
    UNVERIFIED = 'unverified', 'Unverified'
    VERIFIED = 'verified', 'Verified'
    DISPUTED = 'disputed', 'Disputed'

class Assignment(models.Model):
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='assignments')
    dataset_item = models.ForeignKey('datasets.DatasetItem', on_delete=models.CASCADE, related_name='assignments')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignments')
    status = models.CharField(max_length=20, choices=AssignmentStatus.choices, default=AssignmentStatus.PENDING)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    due_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    # Randomization: which original response is shown as display A
    display_a_is_original_a = models.BooleanField(default=True)
    # For balancing, track order
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('dataset_item', 'reviewer')
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['project', 'reviewer', 'status']),
        ]

    def __str__(self):
        return f"{self.dataset_item.task_id} -> {self.reviewer.username} ({self.status})"

    def __init__(self, *args, **kwargs):
        # Track whether display order was explicitly provided by the caller.
        # Without this, save() could silently override an explicit value.
        self._display_order_explicit = 'display_a_is_original_a' in kwargs
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        # Randomize display order on creation ONLY when not explicitly provided.
        # Explicit values (from views, seed, tests) are always preserved so the
        # immutable mapping between display position and original response ID
        # stays consistent for reporting.
        if self._state.adding and not getattr(self, '_display_order_explicit', True):
            self.display_a_is_original_a = random.choice([True, False])
        super().save(*args, **kwargs)

    def mark_in_progress(self):
        if self.status == AssignmentStatus.PENDING:
            self.status = AssignmentStatus.IN_PROGRESS
            self.save(update_fields=['status', 'updated_at'])

    def mark_submitted(self):
        self.status = AssignmentStatus.SUBMITTED
        self.submitted_at = timezone.now()
        self.save(update_fields=['status', 'submitted_at', 'updated_at'])

class Review(models.Model):
    assignment = models.OneToOneField(Assignment, on_delete=models.CASCADE, related_name='review')
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='reviews')
    dataset_item = models.ForeignKey('datasets.DatasetItem', on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rubric = models.ForeignKey('rubrics.Rubric', on_delete=models.PROTECT, related_name='reviews')
    # Preference stored as ORIGINAL label (not display) for reporting consistency
    preference = models.CharField(max_length=20, choices=PreferenceChoice.choices)
    # Display preference is what reviewer clicked; original is computed
    display_preference = models.CharField(max_length=20, choices=PreferenceChoice.choices, blank=True)
    confidence = models.IntegerField(default=3, help_text="1-5 confidence")
    rationale = models.TextField(blank=True)
    is_draft = models.BooleanField(default=True)
    display_a_is_original_a = models.BooleanField(default=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at', '-created_at']
        indexes = [
            models.Index(fields=['project', 'reviewer']),
            models.Index(fields=['dataset_item']),
        ]

    def __str__(self):
        return f"Review {self.dataset_item.task_id} by {self.reviewer.username}: {self.preference}"

    def save(self, *args, **kwargs):
        if not self.is_draft and not self.submitted_at:
            self.submitted_at = timezone.now()
        super().save(*args, **kwargs)

class ReviewDimensionScore(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='dimension_scores')
    dimension = models.ForeignKey('rubrics.RubricDimension', on_delete=models.CASCADE, related_name='scores')
    score_a = models.IntegerField(null=True, blank=True)
    score_b = models.IntegerField(null=True, blank=True)
    is_na = models.BooleanField(default=False)

    class Meta:
        unique_together = ('review', 'dimension')

    def __str__(self):
        return f"{self.review.id} - {self.dimension.key}: A={self.score_a} B={self.score_b}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.is_na:
            return
        if self.score_a is not None:
            if not (self.dimension.scale_min <= self.score_a <= self.dimension.scale_max):
                raise ValidationError(f"score_a out of range for {self.dimension.name}")
        if self.score_b is not None:
            if not (self.dimension.scale_min <= self.score_b <= self.dimension.scale_max):
                raise ValidationError(f"score_b out of range for {self.dimension.name}")

class Issue(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='issues')
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='issues')
    dataset_item = models.ForeignKey('datasets.DatasetItem', on_delete=models.CASCADE, related_name='issues')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reported_issues')
    response_target = models.CharField(max_length=20, choices=[('response_a', 'Response A (original)'), ('response_b', 'Response B (original)')])
    category = models.CharField(max_length=30, choices=IssueCategory.choices)
    severity = models.CharField(max_length=20, choices=IssueSeverity.choices, default=IssueSeverity.MEDIUM)
    excerpt = models.TextField(blank=True, help_text="Relevant excerpt from response")
    evidence = models.TextField(blank=True, help_text="Evidence/source supporting the issue")
    explanation = models.TextField(blank=True)
    verification_status = models.CharField(max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED)
    correction = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.category} ({self.severity}) on {self.response_target}"

class Adjudication(models.Model):
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='adjudications')
    dataset_item = models.ForeignKey('datasets.DatasetItem', on_delete=models.CASCADE, related_name='adjudications')
    adjudicator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='adjudications')
    final_preference = models.CharField(max_length=20, choices=PreferenceChoice.choices)
    rationale = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    # Preserve original reviews - we link via dataset_item, but also store snapshot
    reviews_snapshot = models.JSONField(default=list, blank=True, help_text="Snapshot of reviews at adjudication time")

    class Meta:
        ordering = ['-created_at']
        unique_together = ('project', 'dataset_item')

    def __str__(self):
        return f"Adjudication {self.dataset_item.task_id}: {self.final_preference}"

class AuditLog(models.Model):
    project = models.ForeignKey('projects.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp} - {self.user} - {self.action}"
