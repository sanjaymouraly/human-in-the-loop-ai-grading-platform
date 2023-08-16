from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q
import random
import json

from apps.projects.models import Project
from apps.datasets.models import Dataset, DatasetItem
from apps.rubrics.models import Rubric
from .models import Assignment, Review, ReviewDimensionScore, Issue, Adjudication, PreferenceChoice, AssignmentStatus
from .forms import AssignmentCreateForm, ReviewForm, IssueForm, AdjudicationForm
from apps.core.utils import log_audit

@login_required
def reviewer_queue(request):
    assignments = Assignment.objects.filter(reviewer=request.user).select_related('project', 'dataset_item').order_by('status', '-assigned_at')
    # Filters
    project_id = request.GET.get('project')
    status = request.GET.get('status')
    search = request.GET.get('search', '').strip()
    sort = request.GET.get('sort', 'assigned_at')
    
    if project_id:
        assignments = assignments.filter(project_id=project_id)
    if status:
        assignments = assignments.filter(status=status)
    if search:
        assignments = assignments.filter(
            Q(dataset_item__task_id__icontains=search) |
            Q(dataset_item__prompt__icontains=search) |
            Q(project__name__icontains=search)
        )
    
    # Sorting
    if sort == 'task_id':
        assignments = assignments.order_by('dataset_item__task_id')
    elif sort == 'project':
        assignments = assignments.order_by('project__name')
    else:
        assignments = assignments.order_by('status', '-assigned_at')

    pending = assignments.filter(status__in=['pending', 'in_progress'])
    submitted = assignments.filter(status='submitted')
    skipped = assignments.filter(status='skipped')

    # Projects for filter
    projects = Project.objects.filter(
        Q(created_by=request.user) | Q(memberships__user=request.user) | Q(assignments__reviewer=request.user)
    ).distinct()

    return render(request, 'evaluations/queue.html', {
        'pending_assignments': pending[:50],
        'submitted_assignments': submitted[:20],
        'skipped_assignments': skipped[:20],
        'projects': projects,
        'filter_project': project_id,
        'filter_status': status,
        'search': search,
        'sort': sort,
    })

@login_required
def assignment_list(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.is_member(request.user):
        return HttpResponseForbidden("Not member")
    assignments = project.assignments.select_related('reviewer', 'dataset_item').order_by('-assigned_at')
    
    # Search and filters
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    reviewer_filter = request.GET.get('reviewer', '')
    
    if search:
        assignments = assignments.filter(
            Q(dataset_item__task_id__icontains=search) |
            Q(reviewer__username__icontains=search) |
            Q(dataset_item__prompt__icontains=search)
        )
    if status_filter:
        assignments = assignments.filter(status=status_filter)
    if reviewer_filter:
        assignments = assignments.filter(reviewer__username__icontains=reviewer_filter)
    
    paginator = Paginator(assignments, 30)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'evaluations/assignment_list.html', {
        'project': project, 
        'page_obj': page_obj,
        'search': search,
        'status_filter': status_filter,
        'reviewer_filter': reviewer_filter,
    })

@login_required
def assignment_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("No permission")
    datasets = project.datasets.filter(is_active=True)

    if request.method == 'POST':
        form = AssignmentCreateForm(request.POST)
        if form.is_valid():
            dataset_id = form.cleaned_data['dataset_id']
            usernames_raw = form.cleaned_data['reviewer_usernames']
            assign_all = form.cleaned_data['assign_all']
            task_ids_raw = form.cleaned_data.get('task_ids', '')

            try:
                dataset = Dataset.objects.get(pk=dataset_id, project=project)
            except Dataset.DoesNotExist:
                messages.error(request, "Dataset not found")
                return render(request, 'evaluations/assignment_create.html', {'project': project, 'form': form, 'datasets': datasets})

            usernames = [u.strip() for u in usernames_raw.split(',') if u.strip()]
            users = []
            missing = []
            for uname in usernames:
                try:
                    u = User.objects.get(username=uname)
                    users.append(u)
                except User.DoesNotExist:
                    missing.append(uname)
            if missing:
                messages.error(request, f"Users not found: {', '.join(missing)}")
                return render(request, 'evaluations/assignment_create.html', {'project': project, 'form': form, 'datasets': datasets})

            if not users:
                messages.error(request, "No valid reviewers provided")
                return render(request, 'evaluations/assignment_create.html', {'project': project, 'form': form, 'datasets': datasets})

            # Get items
            if assign_all:
                items = dataset.items.filter(is_active=True)
            else:
                if task_ids_raw:
                    task_ids = [t.strip() for t in task_ids_raw.split(',') if t.strip()]
                    items = dataset.items.filter(is_active=True, task_id__in=task_ids)
                else:
                    items = dataset.items.filter(is_active=True)

            if not items.exists():
                messages.error(request, "No items matched")
                return render(request, 'evaluations/assignment_create.html', {'project': project, 'form': form, 'datasets': datasets})

            created_count = 0
            with transaction.atomic():
                for item in items:
                    for reviewer in users:
                        # Avoid duplicate
                        if Assignment.objects.filter(dataset_item=item, reviewer=reviewer).exists():
                            continue
                        # Randomize display order
                        display_a_is_original_a = random.choice([True, False])
                        Assignment.objects.create(
                            project=project,
                            dataset_item=item,
                            reviewer=reviewer,
                            assigned_by=request.user,
                            display_a_is_original_a=display_a_is_original_a,
                            status=AssignmentStatus.PENDING
                        )
                        created_count += 1

            log_audit(request, 'assignments_created', project, details={'dataset_id': dataset.id, 'count': created_count, 'reviewers': usernames})
            messages.success(request, f'Created {created_count} assignments for {len(users)} reviewers across {items.count()} items.')
            return redirect('assignment_list', project_pk=project.pk)
    else:
        form = AssignmentCreateForm()

    return render(request, 'evaluations/assignment_create.html', {'project': project, 'form': form, 'datasets': datasets})

@login_required
def review_workspace(request, assignment_pk):
    assignment = get_object_or_404(Assignment, pk=assignment_pk)
    project = assignment.project

    # Permission: reviewer or manager
    if assignment.reviewer != request.user and not project.can_edit(request.user):
        return HttpResponseForbidden("Not authorized to view this assignment")

    dataset_item = assignment.dataset_item

    # Get active rubric - latest active
    rubric = project.rubrics.filter(is_active=True).order_by('-version').first()
    if not rubric:
        messages.error(request, "No active rubric found for this project. Please create one.")
        return redirect('project_detail', pk=project.pk)

    # Existing review (draft or submitted)
    try:
        existing_review = assignment.review
    except Review.DoesNotExist:
        existing_review = None

    # If review already submitted and user is reviewer, allow viewing but not editing unless manager
    is_submitted = existing_review and not existing_review.is_draft

    # Prepare display responses
    display_a, display_b, model_display_a, model_display_b = dataset_item.get_responses_for_display(assignment.display_a_is_original_a)

    # For blind review, hide model names
    if project.blind_review and assignment.reviewer == request.user:
        model_display_a = model_display_b = "Hidden (blind review)"

    # Handle form submission
    if request.method == 'POST':
        # Prevent duplicate final submissions: once a review is submitted it is
        # final. Reviewers may keep editing drafts, but not submitted reviews.
        if existing_review and not existing_review.is_draft:
            messages.error(request, "This review has already been submitted and cannot be modified.")
            return redirect('reviewer_queue')
        # Check if draft save via AJAX or normal
        is_draft = request.POST.get('save_type') == 'draft'

        form = ReviewForm(request.POST, rubric=rubric)
        if form.is_valid():
            with transaction.atomic():
                # Determine display vs original preference
                display_pref = form.cleaned_data['preference']
                # Convert to original
                original_pref = dataset_item.get_original_label_for_display(display_pref, assignment.display_a_is_original_a)

                # Time tracking
                time_spent = request.POST.get('time_spent_seconds', '0')
                try:
                    time_spent_int = int(time_spent)
                except:
                    time_spent_int = 0
                
                # Create or update review
                if existing_review:
                    review = existing_review
                    review.preference = original_pref
                    review.display_preference = display_pref
                    review.confidence = form.cleaned_data['confidence']
                    review.rationale = form.cleaned_data['rationale']
                    review.is_draft = is_draft
                    review.rubric = rubric
                    review.display_a_is_original_a = assignment.display_a_is_original_a
                    review.time_spent_seconds = max(review.time_spent_seconds, time_spent_int) if review.time_spent_seconds else time_spent_int
                    if not is_draft:
                        review.submitted_at = timezone.now()
                    review.save()
                    # Delete existing dimension scores
                    review.dimension_scores.all().delete()
                else:
                    review = Review.objects.create(
                        assignment=assignment,
                        project=project,
                        dataset_item=dataset_item,
                        reviewer=assignment.reviewer,
                        rubric=rubric,
                        preference=original_pref,
                        display_preference=display_pref,
                        confidence=form.cleaned_data['confidence'],
                        rationale=form.cleaned_data['rationale'],
                        is_draft=is_draft,
                        display_a_is_original_a=assignment.display_a_is_original_a,
                        submitted_at=None if is_draft else timezone.now(),
                        time_spent_seconds=time_spent_int
                    )

                # Save dimension scores
                for dim in rubric.dimensions.all():
                    na_key = f'dim_{dim.id}_na'
                    is_na = form.cleaned_data.get(na_key, False) if dim.allow_na else False
                    score_a = None
                    score_b = None
                    if not is_na:
                        score_a = form.cleaned_data.get(f'dim_{dim.id}_a')
                        score_b = form.cleaned_data.get(f'dim_{dim.id}_b')
                    ReviewDimensionScore.objects.create(
                        review=review,
                        dimension=dim,
                        score_a=score_a,
                        score_b=score_b,
                        is_na=is_na
                    )

                # Update assignment status
                if not is_draft:
                    assignment.status = AssignmentStatus.SUBMITTED
                    assignment.submitted_at = timezone.now()
                    assignment.save(update_fields=['status', 'submitted_at', 'updated_at'])
                    log_audit(request, 'review_submitted', project, details={'assignment_id': assignment.id, 'review_id': review.id})
                    messages.success(request, "Review submitted successfully.")
                    return redirect('reviewer_queue')
                else:
                    assignment.status = AssignmentStatus.IN_PROGRESS
                    assignment.save(update_fields=['status', 'updated_at'])
                    log_audit(request, 'review_draft_saved', project, details={'assignment_id': assignment.id})
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'status': 'draft_saved', 'review_id': review.id})
                    messages.info(request, "Draft saved.")
                    return redirect('review_workspace', assignment_pk=assignment.pk)
        else:
            # Form invalid
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
    else:
        # GET - prefill form if existing review exists
        initial = {}
        if existing_review:
            # Convert original preference back to display preference for form
            # existing_review.display_preference is what they selected
            initial['preference'] = existing_review.display_preference or existing_review.preference
            initial['confidence'] = existing_review.confidence
            initial['rationale'] = existing_review.rationale
            for score in existing_review.dimension_scores.select_related('dimension'):
                dim_id = score.dimension.id
                if score.score_a is not None:
                    initial[f'dim_{dim_id}_a'] = score.score_a
                if score.score_b is not None:
                    initial[f'dim_{dim_id}_b'] = score.score_b
                if score.is_na:
                    initial[f'dim_{dim_id}_na'] = True
        form = ReviewForm(initial=initial, rubric=rubric)

    # Issues for this review
    issues = []
    if existing_review:
        issues = existing_review.issues.select_related('reviewer').order_by('-created_at')

    # Other reviewers' reviews - only show if current review is submitted or user is manager, and we hide until finalization?
    # Requirement: Never reveal other reviewers' judgments before independent review is finalized.
    other_reviews = []
    can_view_others = False
    if project.can_edit(request.user) or (existing_review and not existing_review.is_draft):
        can_view_others = True
        other_reviews = Review.objects.filter(
            dataset_item=dataset_item,
            is_draft=False
        ).exclude(pk=existing_review.pk if existing_review else None).select_related('reviewer')

    context = {
        'assignment': assignment,
        'project': project,
        'dataset_item': dataset_item,
        'rubric': rubric,
        'form': form,
        'display_a': display_a,
        'display_b': display_b,
        'model_display_a': model_display_a,
        'model_display_b': model_display_b,
        'existing_review': existing_review,
        'is_submitted': is_submitted,
        'issues': issues,
        'other_reviews': other_reviews,
        'can_view_others': can_view_others,
        'display_a_is_original_a': assignment.display_a_is_original_a,
    }
    return render(request, 'evaluations/review_workspace.html', context)

@login_required
def issue_create(request, assignment_pk):
    assignment = get_object_or_404(Assignment, pk=assignment_pk)
    if assignment.reviewer != request.user:
        return HttpResponseForbidden("Only reviewer can add issues")
    try:
        review = assignment.review
    except Review.DoesNotExist:
        messages.error(request, "Save a review draft first before adding issues")
        return redirect('review_workspace', assignment_pk=assignment.pk)

    if request.method == 'POST':
        form = IssueForm(request.POST)
        if form.is_valid():
            Issue.objects.create(
                review=review,
                project=assignment.project,
                dataset_item=assignment.dataset_item,
                reviewer=request.user,
                response_target=form.cleaned_data['response_target'],
                category=form.cleaned_data['category'],
                severity=form.cleaned_data['severity'],
                excerpt=form.cleaned_data['excerpt'],
                evidence=form.cleaned_data['evidence'],
                explanation=form.cleaned_data['explanation'],
                correction=form.cleaned_data['correction'],
            )
            messages.success(request, "Issue reported")
            return redirect('review_workspace', assignment_pk=assignment.pk)
    else:
        form = IssueForm()
    return render(request, 'evaluations/issue_form.html', {'assignment': assignment, 'form': form})

@login_required
def issue_delete(request, assignment_pk, issue_pk):
    assignment = get_object_or_404(Assignment, pk=assignment_pk)
    issue = get_object_or_404(Issue, pk=issue_pk, review__assignment=assignment)
    if issue.reviewer != request.user and not assignment.project.can_edit(request.user):
        return HttpResponseForbidden("No permission")
    if request.method == 'POST':
        issue.delete()
        messages.success(request, "Issue deleted")
    return redirect('review_workspace', assignment_pk=assignment.pk)

@login_required
def disagreement_list(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("Only managers can view disagreements")

    # Find dataset items with >1 submitted reviews and disagreement in preference
    from django.db.models import Count
    # Get items with at least 2 reviews
    items_with_reviews = DatasetItem.objects.filter(
        project=project,
        reviews__is_draft=False
    ).annotate(
        review_count=Count('reviews', filter=Q(reviews__is_draft=False), distinct=True)
    ).filter(review_count__gte=2)

    disagreements = []
    for item in items_with_reviews:
        reviews = item.reviews.filter(is_draft=False).select_related('reviewer')
        prefs = set(r.preference for r in reviews)
        if len(prefs) > 1:
            # Check if adjudicated
            adjudicated = item.adjudications.exists()
            disagreements.append({
                'item': item,
                'reviews': reviews,
                'prefs': prefs,
                'adjudicated': adjudicated,
                'adjudication': item.adjudications.first() if adjudicated else None,
            })

    return render(request, 'evaluations/disagreements.html', {'project': project, 'disagreements': disagreements})

@login_required
def adjudication_view(request, project_pk, item_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("Only managers can adjudicate")
    item = get_object_or_404(DatasetItem, pk=item_pk, project=project)
    reviews = item.reviews.filter(is_draft=False).select_related('reviewer', 'rubric').prefetch_related('dimension_scores__dimension', 'issues')

    try:
        adjudication = item.adjudications.get(project=project)
    except Adjudication.DoesNotExist:
        adjudication = None

    if request.method == 'POST':
        form = AdjudicationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Snapshot reviews
                snapshot = []
                for r in reviews:
                    snapshot.append({
                        'reviewer': r.reviewer.username,
                        'preference': r.preference,
                        'confidence': r.confidence,
                        'rationale': r.rationale,
                        'scores': list(r.dimension_scores.values('dimension__key', 'score_a', 'score_b', 'is_na')),
                    })
                if adjudication:
                    adjudication.final_preference = form.cleaned_data['final_preference']
                    adjudication.rationale = form.cleaned_data['rationale']
                    adjudication.adjudicator = request.user
                    adjudication.reviews_snapshot = snapshot
                    adjudication.save()
                else:
                    adjudication = Adjudication.objects.create(
                        project=project,
                        dataset_item=item,
                        adjudicator=request.user,
                        final_preference=form.cleaned_data['final_preference'],
                        rationale=form.cleaned_data['rationale'],
                        reviews_snapshot=snapshot
                    )
                log_audit(request, 'adjudication_created', project, details={'item_id': item.id, 'adjudication_id': adjudication.id})
                messages.success(request, "Adjudication saved")
                return redirect('disagreement_list', project_pk=project.pk)
    else:
        initial = {}
        if adjudication:
            initial['final_preference'] = adjudication.final_preference
            initial['rationale'] = adjudication.rationale
        form = AdjudicationForm(initial=initial)

    return render(request, 'evaluations/adjudication.html', {
        'project': project,
        'item': item,
        'reviews': reviews,
        'adjudication': adjudication,
        'form': form,
    })

@login_required
def review_detail(request, review_pk):
    review = get_object_or_404(Review, pk=review_pk)
    project = review.project
    if not project.is_member(request.user):
        return HttpResponseForbidden("Not member")
    # Only allow viewing others if manager or own review or review submitted
    if review.reviewer != request.user and not project.can_edit(request.user):
        # If not manager, only allow if both reviews submitted? For simplicity, block
        if review.is_draft:
            return HttpResponseForbidden("Cannot view draft of other reviewer")

    return render(request, 'evaluations/review_detail.html', {'review': review, 'project': project})
