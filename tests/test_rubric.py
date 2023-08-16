import pytest
from django.contrib.auth.models import User
from apps.projects.models import Project
from apps.rubrics.models import Rubric, RubricDimension

@pytest.mark.django_db
def test_rubric_versioning():
    user = User.objects.create_user(username='u', password='p')
    proj = Project.objects.create(name='P', created_by=user)
    r1 = Rubric.objects.create(project=proj, name='Rubric', created_by=user)
    assert r1.version == 1
    r2 = Rubric.objects.create(project=proj, name='Rubric 2', created_by=user)
    assert r2.version == 2

@pytest.mark.django_db
def test_dimension_scale_validation():
    user = User.objects.create_user(username='u', password='p')
    proj = Project.objects.create(name='P', created_by=user)
    rubric = Rubric.objects.create(project=proj, name='R', created_by=user)
    dim = RubricDimension.objects.create(rubric=rubric, key='test', name='Test', scale_min=1, scale_max=5)
    assert dim.get_scale_range() == range(1,6)

@pytest.mark.django_db
def test_rubric_preserved_in_review():
    from apps.datasets.models import Dataset, DatasetItem
    from apps.evaluations.models import Assignment, Review
    user = User.objects.create_user(username='reviewer', password='p')
    proj = Project.objects.create(name='P', created_by=user)
    rubric_v1 = Rubric.objects.create(project=proj, name='R', created_by=user)
    dim = RubricDimension.objects.create(rubric=rubric_v1, key='accuracy', name='Accuracy', scale_min=1, scale_max=5)

    dataset = Dataset.objects.create(project=proj, name='DS', version=1, row_count=1, created_by=user)
    item = DatasetItem.objects.create(dataset=dataset, project=proj, task_id='1', prompt='Q', response_a='A', response_b='B')

    assignment = Assignment.objects.create(project=proj, dataset_item=item, reviewer=user, display_a_is_original_a=True)

    review = Review.objects.create(
        assignment=assignment,
        project=proj,
        dataset_item=item,
        reviewer=user,
        rubric=rubric_v1,
        preference='response_a',
        display_preference='response_a',
        confidence=5,
        rationale='Test',
        is_draft=False,
        display_a_is_original_a=True
    )

    # Create new rubric version
    rubric_v2 = Rubric.objects.create(project=proj, name='R2', created_by=user)
    assert rubric_v2.version == 2

    # Old review still points to v1
    review.refresh_from_db()
    assert review.rubric.version == 1
