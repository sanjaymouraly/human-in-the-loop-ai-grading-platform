from django.contrib import admin
from .models import Project, ProjectMembership

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'task_type', 'status', 'blind_review', 'created_by', 'created_at')
    list_filter = ('task_type', 'status', 'blind_review')
    search_fields = ('name', 'description')

@admin.register(ProjectMembership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('project', 'user', 'role', 'added_at')
    list_filter = ('role',)
