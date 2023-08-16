from django.contrib import admin
from .models import Dataset, DatasetItem

@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'project', 'row_count', 'created_by', 'created_at')
    list_filter = ('project',)
    search_fields = ('name',)

@admin.register(DatasetItem)
class DatasetItemAdmin(admin.ModelAdmin):
    list_display = ('task_id', 'project', 'dataset', 'model_a', 'model_b', 'created_at')
    list_filter = ('project',)
    search_fields = ('task_id', 'prompt')
