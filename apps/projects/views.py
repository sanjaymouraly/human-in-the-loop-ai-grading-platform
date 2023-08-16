from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from .models import Project, ProjectMembership, MembershipRole
from .forms import ProjectForm, MembershipForm
from apps.evaluations.models import AuditLog
from apps.core.utils import log_audit

@login_required
def project_list(request):
    user = request.user
    if user.is_superuser or (hasattr(user, 'profile') and user.profile.role == 'admin'):
        projects = Project.objects.all()
    else:
        projects = Project.objects.filter(
            Q(created_by=user) | Q(memberships__user=user)
        ).distinct()
    
    # Search, filter, sort
    search = request.GET.get('search', '').strip()
    task_type = request.GET.get('task_type', '')
    status_filter = request.GET.get('status', '')
    sort = request.GET.get('sort', '-created_at')
    
    if search:
        projects = projects.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search)
        )
    if task_type:
        projects = projects.filter(task_type=task_type)
    if status_filter:
        projects = projects.filter(status=status_filter)
    
    # Sorting
    allowed_sorts = ['-created_at', 'created_at', 'name', '-name', 'task_type']
    if sort in allowed_sorts:
        projects = projects.order_by(sort)
    else:
        projects = projects.order_by('-created_at')
    
    projects = projects.annotate(
        dataset_count=Count('datasets', distinct=True),
        item_count=Count('dataset_items', distinct=True),
        member_count=Count('memberships', distinct=True)
    )
    
    return render(request, 'projects/list.html', {
        'projects': projects,
        'search': search,
        'task_type_filter': task_type,
        'status_filter': status_filter,
        'sort': sort,
    })

@login_required
def project_create(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            # Auto-add creator as manager
            ProjectMembership.objects.create(
                project=project,
                user=request.user,
                role=MembershipRole.MANAGER,
                added_by=request.user
            )
            log_audit(request, 'project_created', project)
            messages.success(request, f'Project "{project.name}" created.')
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm()
    return render(request, 'projects/form.html', {'form': form, 'title': 'Create Project'})

@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not project.is_member(request.user):
        return HttpResponseForbidden("You are not a member of this project.")

    # Stats
    datasets = project.datasets.filter(is_active=True)
    total_items = project.dataset_items.filter(is_active=True).count()
    assignments = project.assignments.all()
    reviews = project.reviews.filter(is_draft=False)
    members = project.memberships.select_related('user')

    # Progress
    total_assignments = assignments.count()
    submitted_assignments = assignments.filter(status='submitted').count()
    completion_pct = (submitted_assignments / total_assignments * 100) if total_assignments else 0

    # Recent activity
    recent_reviews = reviews.select_related('reviewer', 'dataset_item').order_by('-submitted_at')[:10]
    audit_logs = project.audit_logs.select_related('user').order_by('-timestamp')[:20]

    context = {
        'project': project,
        'datasets': datasets,
        'total_items': total_items,
        'members': members,
        'total_assignments': total_assignments,
        'submitted_assignments': submitted_assignments,
        'completion_pct': round(completion_pct, 1),
        'recent_reviews': recent_reviews,
        'audit_logs': audit_logs,
        'can_edit': project.can_edit(request.user),
    }
    return render(request, 'projects/detail.html', context)

@login_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("You don't have permission to edit this project.")
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            log_audit(request, 'project_updated', project)
            messages.success(request, 'Project updated.')
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project)
    return render(request, 'projects/form.html', {'form': form, 'title': f'Edit {project.name}', 'project': project})

@login_required
def project_members(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("No permission")
    members = project.memberships.select_related('user')

    if request.method == 'POST':
        form = MembershipForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            role = form.cleaned_data['role']
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                messages.error(request, f'User "{username}" not found.')
                return redirect('project_members', pk=pk)
            membership, created = ProjectMembership.objects.get_or_create(
                project=project,
                user=user,
                defaults={'role': role, 'added_by': request.user}
            )
            if not created:
                membership.role = role
                membership.save()
                messages.info(request, f'Updated {user.username} role to {role}.')
            else:
                messages.success(request, f'Added {user.username} as {role}.')
            log_audit(request, 'member_added', project, details={'username': username, 'role': role})
            return redirect('project_members', pk=pk)
    else:
        form = MembershipForm()

    return render(request, 'projects/members.html', {'project': project, 'members': members, 'form': form})

@login_required
def project_member_remove(request, pk, membership_id):
    project = get_object_or_404(Project, pk=pk)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("No permission")
    membership = get_object_or_404(ProjectMembership, pk=membership_id, project=project)
    if request.method == 'POST':
        username = membership.user.username
        membership.delete()
        messages.success(request, f'Removed {username}.')
        log_audit(request, 'member_removed', project, details={'username': username})
    return redirect('project_members', pk=pk)
