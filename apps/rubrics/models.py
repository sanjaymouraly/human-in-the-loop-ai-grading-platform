from django.db import models
from django.contrib.auth.models import User

class Rubric(models.Model):
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='rubrics')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    instructions = models.TextField(blank=True, help_text="Guidance for reviewers on how to apply this rubric")

    class Meta:
        ordering = ['-version', '-created_at']
        unique_together = ('project', 'version')

    def __str__(self):
        return f"{self.name} v{self.version} ({self.project.name})"

    def save(self, *args, **kwargs):
        if not self.pk:
            # Auto-increment version per project
            last = Rubric.objects.filter(project=self.project).order_by('-version').first()
            if last:
                self.version = last.version + 1
        super().save(*args, **kwargs)

class RubricDimension(models.Model):
    rubric = models.ForeignKey(Rubric, on_delete=models.CASCADE, related_name='dimensions')
    key = models.SlugField(max_length=50, help_text="Unique key within rubric, e.g., instruction_following")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    scale_min = models.IntegerField(default=1)
    scale_max = models.IntegerField(default=5)
    allow_na = models.BooleanField(default=False)
    weight = models.FloatField(default=1.0)
    anchored_descriptions = models.JSONField(default=dict, blank=True, help_text="Map score -> description")
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ('rubric', 'key')

    def __str__(self):
        return f"{self.rubric.name} - {self.name} ({self.scale_min}-{self.scale_max})"

    def clean_scale(self):
        if self.scale_min >= self.scale_max:
            raise ValueError("scale_min must be less than scale_max")

    def get_scale_range(self):
        return range(self.scale_min, self.scale_max + 1)
