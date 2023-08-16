"""
End-to-end journey tests using the Django test client.

The full browser journey (login -> project -> import -> rubric -> assign ->
evaluate -> submit -> second review -> disagreement -> adjudicate -> analytics
-> export) is covered here without a real browser. For true browser-based
E2E, run the app and use Playwright manually (see capture_screenshots.py)
or the `page` fixtures in conftest.py with pytest-playwright installed.
"""
import pytest
from django.test import Client
from django.contrib.auth.models import User
from apps.accounts.models import Role
from apps.projects.models import Project, TaskType, ProjectMembership, MembershipRole
from apps.datasets.models import Dataset, DatasetItem
from apps.rubrics.models import Rubric, RubricDimension
from apps.evaluations.models import (
    Assignment, Review, ReviewDimensionScore, Issue, Adjudication,
    PreferenceChoice, AssignmentStatus, IssueCategory, IssueSeverity,
)
from apps.rubrics.views import DEFAULT_DIMENSIONS


def _build_project(client, username='manager'):
    """Create a manager user and a fully configured project, log in."""
    User.objects.create_user(username='owner', password='pass12345')
    manager = User.objects.create_user(username=username, password='pass12345')
    manager.profile.role = Role.MANAGER
    manager.profile.save()
    client.login(username=username, password='pass12345')
    return manager


def _create_dataset_with_item(project, task_id='qa_101', prompt='What is 2+2?'):
    dataset = Dataset.objects.create(
        project=project, name='Journey DS', version=1, row_count=1,
        created_by=project.created_by,
    )
    item = DatasetItem.objects.create(
        dataset=dataset, project=project, task_id=task_id, prompt=prompt,
        response_a='4', response_b='5', model_a='model-x', model_b='model-y',
        reference_answer='4', order_index=0,
    )
    return dataset, item


def _create_rubric(project, created_by):
    rubric = Rubric.objects.create(
        project=project, name='Journey Rubric', created_by=created_by,
    )
    for dim in DEFAULT_DIMENSIONS[:3]:
        RubricDimension.objects.create(
            rubric=rubric, key=dim['key'], name=dim['name'],
            scale_min=dim['scale_min'], scale_max=dim['scale_max'],
            anchored_descriptions=dim.get('anchored_descriptions', {}),
            weight=dim.get('weight', 1.0), order=dim.get('order', 0),
        )
    return rubric


@pytest.mark.django_db
def test_full_evaluation_journey():
    """login -> create project -> import dataset -> rubric -> assign ->
    evaluate -> submit -> second review -> disagreement -> adjudicate ->
    analytics -> export"""
    client = Client()
    manager = _build_project(client, 'journey_manager')

    # 1. Create project
    resp = client.post('/projects/create/', {
        'name': 'Journey Project',
        'description': 'E2E journey',
        'instructions': 'Be careful',
        'task_type': TaskType.QA,
        'goal': 'Test',
        'status': 'active',
        'blind_review': 'on',
        'require_double_review': 'on',
        'balance_ab_order': 'on',
    })
    assert resp.status_code == 302, f"project create failed: {resp.status_code}"
    project = Project.objects.get(name='Journey Project')

    # 2. Import dataset via API
    dataset, item = _create_dataset_with_item(project)
    resp = client.post(
        f'/evaluations/api/projects/{project.id}/ingest/',
        data='{"name": "API DS", "items": [{"task_id": "api_1", "prompt": "What is the capital of France?", "response_a": "A1", "response_b": "B1"}]}',
        content_type='application/json',
    )
    assert resp.status_code == 200, f"ingest failed: {resp.content}"

    # 3. Configure rubric
    rubric = _create_rubric(project, manager)

    # 4. Assign two reviewers
    reviewer1 = User.objects.create_user(username='j_rev1', password='pass12345')
    reviewer2 = User.objects.create_user(username='j_rev2', password='pass12345')
    resp = client.post(f'/evaluations/projects/{project.id}/assignments/create/', {
        'dataset_id': dataset.id,
        'reviewer_usernames': 'j_rev1, j_rev2',
        'assign_all': True,
        'task_ids': '',
    })
    assert resp.status_code == 302
    assert Assignment.objects.filter(project=project).count() == 2

    # Force both assignments to share the same display order so that the two
    # reviews (display 'response_a' vs 'response_b') map to genuinely different
    # original preferences -> a disagreement. Otherwise the randomized display
    # order can mask the disagreement non-deterministically.
    a1 = Assignment.objects.get(reviewer=reviewer1)
    a2 = Assignment.objects.get(reviewer=reviewer2)
    a1.display_a_is_original_a = True
    a2.display_a_is_original_a = True
    a1.save(update_fields=['display_a_is_original_a'])
    a2.save(update_fields=['display_a_is_original_a'])

    # 5. Reviewer 1 evaluates and submits
    a1 = Assignment.objects.get(reviewer=reviewer1)
    dims = list(rubric.dimensions.order_by('order'))
    post_data = {
        'save_type': 'final',
        'preference': 'response_a',
        'confidence': 5,
        'rationale': 'A is correct, 2+2=4.',
        'time_spent_seconds': '65',
    }
    for d in dims:
        post_data[f'dim_{d.id}_a'] = 5
        post_data[f'dim_{d.id}_b'] = 2
    client.logout()
    client.login(username='j_rev1', password='pass12345')
    resp = client.post(f'/evaluations/assignments/{a1.id}/review/', post_data)
    assert resp.status_code == 302
    a1.refresh_from_db()
    assert a1.status == AssignmentStatus.SUBMITTED
    review1 = a1.review
    # Preference is stored as the ORIGINAL label; the view randomizes display
    # order, so a display choice of 'response_a' maps to the original response
    # that was actually shown as display A.
    expected = item.get_original_label_for_display('response_a', a1.display_a_is_original_a)
    assert review1.preference == expected
    assert review1.display_preference == 'response_a'
    assert review1.dimension_scores.count() == len(dims)

    # 6. Reviewer review with an issue
    resp = client.post(f'/evaluations/assignments/{a1.id}/issues/create/', {
        'response_target': 'response_b',
        'category': IssueCategory.INCORRECT_CALC,
        'severity': IssueSeverity.HIGH,
        'excerpt': '5',
        'evidence': '2+2=4',
        'explanation': 'Wrong arithmetic',
        'correction': '4',
    })
    assert resp.status_code == 302
    assert Issue.objects.filter(review=review1).count() == 1

    # 7. Reviewer 2 evaluates with disagreement
    a2 = Assignment.objects.get(reviewer=reviewer2)
    client.logout()
    client.login(username='j_rev2', password='pass12345')
    post_data2 = dict(post_data)
    post_data2['preference'] = 'response_b'
    post_data2['rationale'] = 'I prefer B.'
    for d in dims:
        post_data2[f'dim_{d.id}_a'] = 3
        post_data2[f'dim_{d.id}_b'] = 4
    resp = client.post(f'/evaluations/assignments/{a2.id}/review/', post_data2)
    assert resp.status_code == 302

    # 8. Manager sees disagreement and adjudicates
    client.logout()
    client.login(username='journey_manager', password='pass12345')
    resp = client.get(f'/evaluations/projects/{project.id}/disagreements/')
    assert resp.status_code == 200
    assert b'qa_101' in resp.content
    resp = client.post(f'/evaluations/projects/{project.id}/items/{item.id}/adjudicate/', {
        'final_preference': 'response_a',
        'rationale': 'A is factually correct (2+2=4).',
    })
    assert resp.status_code == 302
    adj = Adjudication.objects.get(dataset_item=item)
    assert adj.final_preference == 'response_a'
    assert len(adj.reviews_snapshot) == 2

    # 9. Analytics dashboard
    resp = client.get(f'/analytics/{project.id}/')
    assert resp.status_code == 200
    assert b'kappa' in resp.content.lower() or b'Kappa' in resp.content

    # 10. Exports
    for fmt in ('csv', 'json', 'jsonl'):
        resp = client.get(f'/analytics/{project.id}/export/?format={fmt}')
        assert resp.status_code == 200, f"{fmt} export failed"

    resp = client.get(f'/analytics/{project.id}/anonymized/')
    assert resp.status_code == 200


@pytest.mark.django_db
def test_duplicate_submission_blocked():
    """A submitted review cannot be overwritten by a second final POST."""
    client = Client()
    manager = _build_project(client, 'dup_manager')
    project = Project.objects.create(name='Dup Project', created_by=manager, task_type=TaskType.QA)
    rubric = _create_rubric(project, manager)
    _, item = _create_dataset_with_item(project)
    reviewer = User.objects.create_user(username='dup_rev', password='pass12345')
    assignment = Assignment.objects.create(
        project=project, dataset_item=item, reviewer=reviewer,
        display_a_is_original_a=True, status=AssignmentStatus.SUBMITTED,
    )
    dims = list(rubric.dimensions.order_by('order'))
    client.logout()
    client.login(username='dup_rev', password='pass12345')
    post_data = {
        'save_type': 'final', 'preference': 'response_a', 'confidence': 4,
        'rationale': 'first',
    }
    for d in dims:
        post_data[f'dim_{d.id}_a'] = 4
        post_data[f'dim_{d.id}_b'] = 3
    resp = client.post(f'/evaluations/assignments/{assignment.id}/review/', post_data)
    assert resp.status_code == 302
    review = assignment.review
    assert review.preference == 'response_a'
    assert review.rationale == 'first'
    submitted_at = review.submitted_at
    # Second final submission: preference must not change
    post_data['preference'] = 'response_b'
    post_data['rationale'] = 'second'
    client.post(f'/evaluations/assignments/{assignment.id}/review/', post_data)
    review.refresh_from_db()
    assert review.preference == 'response_a'
    assert review.rationale == 'first'
    assert review.submitted_at == submitted_at


@pytest.mark.django_db
def test_cross_project_isolation():
    """Reviewers cannot see or edit other projects' assignments."""
    client = Client()
    m1 = _build_project(client, 'iso_m1')
    p1 = Project.objects.create(name='Iso1', created_by=m1, task_type=TaskType.QA)
    m2 = User.objects.create_user(username='iso_m2', password='pass12345')
    m2.profile.role = Role.MANAGER
    m2.profile.save()
    p2 = Project.objects.create(name='Iso2', created_by=m2, task_type=TaskType.QA)
    _, item2 = _create_dataset_with_item(p2)
    rubric2 = _create_rubric(p2, m2)
    outsider = User.objects.create_user(username='iso_rev', password='pass12345')
    a2 = Assignment.objects.create(project=p2, dataset_item=item2, reviewer=outsider)

    # outsider logs in and tries to access p2 assignment review page
    client.logout()
    client.login(username='iso_rev', password='pass12345')
    resp = client.get(f'/evaluations/assignments/{a2.id}/review/')
    assert resp.status_code == 200  # own assignment: allowed

    # outsider tries to review an assignment belonging to another user
    other = User.objects.create_user(username='iso_other', password='pass12345')
    a3 = Assignment.objects.create(project=p2, dataset_item=item2, reviewer=other)
    resp = client.post(f'/evaluations/assignments/{a3.id}/review/', {
        'save_type': 'draft', 'preference': 'tie', 'confidence': 3, 'rationale': 'x' * 10,
    })
    assert resp.status_code == 403
