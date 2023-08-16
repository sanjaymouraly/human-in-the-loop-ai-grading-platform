import pytest
from django.contrib.auth.models import User
from apps.accounts.models import Profile, Role
from apps.projects.models import Project, ProjectMembership, MembershipRole, TaskType

@pytest.mark.django_db
def test_user_creation_and_profile():
    user = User.objects.create_user(username='testuser', password='pass12345')
    assert hasattr(user, 'profile')
    assert user.profile.role == Role.REVIEWER

@pytest.mark.django_db
def test_project_membership_and_permissions():
    admin = User.objects.create_user(username='admin', password='pass')
    admin.profile.role = Role.ADMIN
    admin.profile.save()
    manager = User.objects.create_user(username='manager', password='pass')
    manager.profile.role = Role.MANAGER
    manager.profile.save()
    reviewer = User.objects.create_user(username='reviewer', password='pass')
    reviewer.profile.role = Role.REVIEWER
    reviewer.profile.save()

    project = Project.objects.create(name='Test Project', task_type=TaskType.QA, created_by=manager)

    # Admin can edit any
    assert project.can_edit(admin) is True
    # Manager can edit any (global manager)
    assert project.can_edit(manager) is True
    # Reviewer not member cannot edit
    assert project.can_edit(reviewer) is False

    # Add reviewer as member
    ProjectMembership.objects.create(project=project, user=reviewer, role=MembershipRole.REVIEWER)
    assert project.is_member(reviewer) is True
    assert project.can_edit(reviewer) is False

@pytest.mark.django_db
def test_cross_project_authorization():
    user = User.objects.create_user(username='user1', password='pass')
    proj1 = Project.objects.create(name='Proj1', created_by=user)
    proj2 = Project.objects.create(name='Proj2', created_by=User.objects.create_user(username='other', password='pass'))

    # user is creator of proj1, so member
    assert proj1.is_member(user) is True
    assert proj2.is_member(user) is False
