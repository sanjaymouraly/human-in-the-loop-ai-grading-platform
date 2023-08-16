import pytest
from django.contrib.auth.models import User
from apps.projects.models import Project
from apps.datasets.models import Dataset, DatasetItem
from apps.rubrics.models import Rubric, RubricDimension
from apps.evaluations.models import Assignment, Review, ReviewDimensionScore, PreferenceChoice

@pytest.mark.django_db
def test_randomized_mapping():
    user = User.objects.create_user(username='u', password='p')
    proj = Project.objects.create(name='P', created_by=user)
    dataset = Dataset.objects.create(project=proj, name='DS', version=1, row_count=1, created_by=user)
    item = DatasetItem.objects.create(dataset=dataset, project=proj, task_id='1', prompt='Q', response_a='Resp A original', response_b='Resp B original')

    # Simulate both display orders
    a_display, b_display, _, _ = item.get_responses_for_display(True)
    assert a_display == 'Resp A original'
    assert b_display == 'Resp B original'

    a_display2, b_display2, _, _ = item.get_responses_for_display(False)
    assert a_display2 == 'Resp B original'
    assert b_display2 == 'Resp A original'

    # Preference mapping
    # If display A is original A, and reviewer chooses display A, original is A
    assert item.get_original_label_for_display('response_a', True) == 'response_a'
    assert item.get_original_label_for_display('response_b', True) == 'response_b'
    # If display A is original B, choosing display A means original B
    assert item.get_original_label_for_display('response_a', False) == 'response_b'
    assert item.get_original_label_for_display('response_b', False) == 'response_a'

@pytest.mark.django_db
def test_assignment_unique_constraint():
    from django.db import IntegrityError
    user = User.objects.create_user(username='reviewer', password='p')
    proj = Project.objects.create(name='P', created_by=user)
    dataset = Dataset.objects.create(project=proj, name='DS', version=1, row_count=1, created_by=user)
    item = DatasetItem.objects.create(dataset=dataset, project=proj, task_id='1', prompt='Q', response_a='A', response_b='B')

    Assignment.objects.create(project=proj, dataset_item=item, reviewer=user, display_a_is_original_a=True)
    # Duplicate should fail
    with pytest.raises(IntegrityError):
        Assignment.objects.create(project=proj, dataset_item=item, reviewer=user, display_a_is_original_a=False)

@pytest.mark.django_db
def test_review_scoring_validation():
    user = User.objects.create_user(username='reviewer', password='p')
    proj = Project.objects.create(name='P', created_by=user)
    rubric = Rubric.objects.create(project=proj, name='R', created_by=user)
    dim = RubricDimension.objects.create(rubric=rubric, key='acc', name='Accuracy', scale_min=1, scale_max=5)

    dataset = Dataset.objects.create(project=proj, name='DS', version=1, row_count=1, created_by=user)
    item = DatasetItem.objects.create(dataset=dataset, project=proj, task_id='1', prompt='Q', response_a='A', response_b='B')
    assignment = Assignment.objects.create(project=proj, dataset_item=item, reviewer=user, display_a_is_original_a=True)

    review = Review.objects.create(
        assignment=assignment,
        project=proj,
        dataset_item=item,
        reviewer=user,
        rubric=rubric,
        preference='response_a',
        display_preference='response_a',
        confidence=5,
        rationale='Test',
        is_draft=False,
        display_a_is_original_a=True
    )

    # Valid score
    score = ReviewDimensionScore.objects.create(review=review, dimension=dim, score_a=5, score_b=1)
    assert score.score_a == 5

@pytest.mark.django_db
def test_draft_vs_submitted():
    user = User.objects.create_user(username='reviewer', password='p')
    proj = Project.objects.create(name='P', created_by=user)
    rubric = Rubric.objects.create(project=proj, name='R', created_by=user)
    dataset = Dataset.objects.create(project=proj, name='DS', version=1, row_count=1, created_by=user)
    item = DatasetItem.objects.create(dataset=dataset, project=proj, task_id='1', prompt='Q', response_a='A', response_b='B')
    assignment = Assignment.objects.create(project=proj, dataset_item=item, reviewer=user, display_a_is_original_a=True)

    review = Review.objects.create(
        assignment=assignment,
        project=proj,
        dataset_item=item,
        reviewer=user,
        rubric=rubric,
        preference='response_a',
        display_preference='response_a',
        confidence=3,
        rationale='Draft',
        is_draft=True,
        display_a_is_original_a=True
    )
    assert review.submitted_at is None
    review.is_draft = False
    review.save()
    assert review.submitted_at is not None
