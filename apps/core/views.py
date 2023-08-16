from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from apps.projects.models import Project
from apps.evaluations.models import Assignment, Review

def landing_view(request):
    if request.user.is_authenticated:
        return dashboard_view(request)
    return render(request, 'core/landing.html')

@login_required
def dashboard_view(request):
    user = request.user
    # Projects where user is member or creator, or all if admin
    if user.is_superuser or (hasattr(user, 'profile') and user.profile.role == 'admin'):
        projects = Project.objects.all()
    else:
        projects = Project.objects.filter(
            Q(created_by=user) | Q(memberships__user=user)
        ).distinct()

    # Assignments for reviewer
    my_assignments = Assignment.objects.filter(reviewer=user).select_related('project', 'dataset_item')
    pending_count = my_assignments.filter(status__in=['pending', 'in_progress']).count()
    submitted_count = my_assignments.filter(status='submitted').count()

    # Recent reviews
    recent_reviews = Review.objects.filter(reviewer=user).select_related('project', 'dataset_item').order_by('-updated_at')[:5]

    # Stats
    total_projects = projects.count()
    total_assignments = my_assignments.count()

    context = {
        'projects': projects[:10],
        'total_projects': total_projects,
        'my_assignments': my_assignments.filter(status__in=['pending', 'in_progress']).order_by('assigned_at')[:10],
        'pending_count': pending_count,
        'submitted_count': submitted_count,
        'recent_reviews': recent_reviews,
        'total_assignments': total_assignments,
    }
    return render(request, 'core/dashboard.html', context)
