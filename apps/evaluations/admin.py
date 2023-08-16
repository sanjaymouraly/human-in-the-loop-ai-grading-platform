from django.contrib import admin
from .models import Assignment, Review, ReviewDimensionScore, Issue, Adjudication, AuditLog

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('dataset_item', 'project', 'reviewer', 'status', 'assigned_at')
    list_filter = ('status', 'project')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('dataset_item', 'reviewer', 'preference', 'confidence', 'is_draft', 'submitted_at')
    list_filter = ('preference', 'is_draft', 'project')

@admin.register(ReviewDimensionScore)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ('review', 'dimension', 'score_a', 'score_b', 'is_na')

@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ('review', 'category', 'severity', 'response_target', 'created_at')
    list_filter = ('category', 'severity')

@admin.register(Adjudication)
class AdjudicationAdmin(admin.ModelAdmin):
    list_display = ('dataset_item', 'project', 'final_preference', 'adjudicator', 'created_at')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'project')
    list_filter = ('action',)
