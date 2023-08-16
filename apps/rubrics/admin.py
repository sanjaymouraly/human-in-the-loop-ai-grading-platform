from django.contrib import admin
from .models import Rubric, RubricDimension

@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'project', 'is_active', 'created_by', 'created_at')
    list_filter = ('is_active',)

@admin.register(RubricDimension)
class DimensionAdmin(admin.ModelAdmin):
    list_display = ('rubric', 'key', 'name', 'scale_min', 'scale_max', 'weight', 'order')
    list_filter = ('rubric',)
