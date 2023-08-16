from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class TaskType(models.TextChoices):
    QA = 'qa', 'Factual QA'
    CODING = 'coding', 'Coding'
    SUMMARIZATION = 'summarization', 'Summarization'
    INSTRUCTION = 'instruction', 'Instruction Following'
    REASONING = 'reasoning', 'Reasoning'
    GENERAL = 'general', 'General'

class ProjectStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    ACTIVE = 'active', 'Active'
    COMPLETED = 'completed', 'Completed'
    ARCHIVED = 'archived', 'Archived'

class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True, help_text="Instructions for reviewers")
    task_type = models.CharField(max_length=20, choices=TaskType.choices, default=TaskType.GENERAL)
    goal = models.TextField(blank=True, help_text="Evaluation goal")
    status = models.CharField(max_length=20, choices=ProjectStatus.choices, default=ProjectStatus.DRAFT)
    blind_review = models.BooleanField(default=True, help_text="Mask model identities from reviewers")
    require_double_review = models.BooleanField(default=True, help_text="Require at least 2 independent reviews per item")
    balance_ab_order = models.BooleanField(default=True, help_text="Randomize and balance A/B display order")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def is_member(self, user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if hasattr(user, 'profile') and user.profile.role == 'admin':
            return True
        return self.memberships.filter(user=user).exists() or self.created_by == user

    def can_edit(self, user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if hasattr(user, 'profile') and user.profile.role in ('admin', 'manager'):
            # Admin/manager can edit if member or creator, or if no membership restriction?
            # For simplicity, global manager can edit any
            return True
        membership = self.memberships.filter(user=user).first()
        if membership and membership.role in ('manager',):
            return True
        return self.created_by == user

    def can_view_analytics(self, user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if hasattr(user, 'profile') and user.profile.role in ('admin', 'manager', 'observer'):
            return True
        membership = self.memberships.filter(user=user).first()
        if membership and membership.role in ('manager', 'observer'):
            return True
        return self.created_by == user

class MembershipRole(models.TextChoices):
    MANAGER = 'manager', 'Manager'
    REVIEWER = 'reviewer', 'Reviewer'
    OBSERVER = 'observer', 'Observer'

class ProjectMembership(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_memberships')
    role = models.CharField(max_length=20, choices=MembershipRole.choices, default=MembershipRole.REVIEWER)
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='added_memberships')

    class Meta:
        unique_together = ('project', 'user')
        ordering = ['added_at']

    def __str__(self):
        return f"{self.user.username} -> {self.project.name} ({self.role})"
