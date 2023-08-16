import pytest
import json
from django.contrib.auth.models import User
from apps.accounts.models import Role
from apps.projects.models import Project, TaskType

@pytest.mark.django_db
def test_api_project_list(client):
    user = User.objects.create_user(username='manager', password='pass')
    user.profile.role = Role.MANAGER
    user.profile.save()
    Project.objects.create(name='Test Project', task_type=TaskType.QA, created_by=user)
    
    client.login(username='manager', password='pass')
    resp = client.get('/evaluations/api/projects/')
    assert resp.status_code == 200
    data = resp.json()
    assert 'projects' in data
    assert len(data['projects']) >= 1

@pytest.mark.django_db
def test_api_autosave(client):
    from apps.datasets.models import Dataset, DatasetItem
    from apps.rubrics.models import Rubric, RubricDimension
    from apps.evaluations.models import Assignment
    
    user = User.objects.create_user(username='reviewer', password='pass')
    user.profile.role = Role.REVIEWER
    user.profile.save()
    
    proj = Project.objects.create(name='P', task_type=TaskType.QA, created_by=user)
    rubric = Rubric.objects.create(project=proj, name='R', created_by=user)
    RubricDimension.objects.create(rubric=rubric, key='acc', name='Accuracy', scale_min=1, scale_max=5)
    
    dataset = Dataset.objects.create(project=proj, name='DS', version=1, row_count=1, created_by=user)
    item = DatasetItem.objects.create(dataset=dataset, project=proj, task_id='1', prompt='Q', response_a='A', response_b='B')
    assignment = Assignment.objects.create(project=proj, dataset_item=item, reviewer=user, display_a_is_original_a=True)
    
    client.login(username='reviewer', password='pass')
    resp = client.post(
        f'/evaluations/assignments/{assignment.id}/autosave/',
        data=json.dumps({'preference': 'response_a', 'confidence': 5, 'rationale': 'Test', 'time_spent_seconds': 42}),
        content_type='application/json'
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'draft_saved'
    
    # Check review created
    assignment.refresh_from_db()
    assert hasattr(assignment, 'review')
    assert assignment.review.rationale == 'Test'
    assert assignment.review.time_spent_seconds == 42

@pytest.mark.django_db
def test_anonymized_export(client):
    from apps.datasets.models import Dataset, DatasetItem
    from apps.rubrics.models import Rubric, RubricDimension
    from apps.evaluations.models import Assignment, Review
    
    manager = User.objects.create_user(username='manager', password='pass')
    manager.profile.role = Role.MANAGER
    manager.profile.save()
    
    reviewer = User.objects.create_user(username='reviewer', password='pass')
    
    proj = Project.objects.create(name='P', task_type=TaskType.QA, created_by=manager)
    rubric = Rubric.objects.create(project=proj, name='R', created_by=manager)
    RubricDimension.objects.create(rubric=rubric, key='acc', name='Accuracy', scale_min=1, scale_max=5)
    
    dataset = Dataset.objects.create(project=proj, name='DS', version=1, row_count=1, created_by=manager)
    item = DatasetItem.objects.create(dataset=dataset, project=proj, task_id='1', prompt='Q', response_a='A', response_b='B')
    assignment = Assignment.objects.create(project=proj, dataset_item=item, reviewer=reviewer, display_a_is_original_a=True)
    
    Review.objects.create(
        assignment=assignment,
        project=proj,
        dataset_item=item,
        reviewer=reviewer,
        rubric=rubric,
        preference='response_a',
        display_preference='response_a',
        confidence=5,
        rationale='Test',
        is_draft=False,
        display_a_is_original_a=True
    )
    
    client.login(username='manager', password='pass')
    resp = client.get(f'/analytics/{proj.id}/anonymized/')
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert 'reviews' in data
    # Check anonymization
    assert data['reviews'][0]['reviewer'].startswith('reviewer_')
    assert data['reviews'][0]['reviewer'] != 'reviewer'

@pytest.mark.django_db
def test_calibration_view(client):
    user = User.objects.create_user(username='manager', password='pass')
    user.profile.role = Role.MANAGER
    user.profile.save()
    
    proj = Project.objects.create(name='P', task_type=TaskType.QA, created_by=user)
    
    from apps.datasets.models import Dataset, DatasetItem
    dataset = Dataset.objects.create(project=proj, name='DS', version=1, row_count=1, created_by=user)
    DatasetItem.objects.create(dataset=dataset, project=proj, task_id='qa_001', prompt='Q', response_a='A', response_b='B', reference_answer='Paris')
    
    client.login(username='manager', password='pass')
    resp = client.get(f'/analytics/{proj.id}/calibration/')
    assert resp.status_code == 200
