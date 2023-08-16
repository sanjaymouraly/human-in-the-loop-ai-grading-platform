"""
Optional secured API for dataset ingestion and report retrieval
"""
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.db import transaction
import json

from apps.projects.models import Project
from apps.datasets.models import Dataset, DatasetItem
from apps.datasets.services import validate_dataset_rows
from apps.core.utils import log_audit

@login_required
def api_project_list(request):
    """List projects user has access to"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    from django.db.models import Q
    user = request.user
    if user.is_superuser or (hasattr(user, 'profile') and user.profile.role == 'admin'):
        projects = Project.objects.all()
    else:
        projects = Project.objects.filter(
            Q(created_by=user) | Q(memberships__user=user)
        ).distinct()
    
    data = [
        {
            'id': p.id,
            'name': p.name,
            'task_type': p.task_type,
            'status': p.status,
            'blind_review': p.blind_review,
            'created_at': p.created_at.isoformat(),
        }
        for p in projects
    ]
    return JsonResponse({'projects': data})

@login_required
def api_dataset_ingest(request, project_pk):
    """Ingest dataset via API - secured, requires manager permission"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    project = get_object_or_404(Project, pk=project_pk)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("No permission")
    
    try:
        body = json.loads(request.body)
        name = body.get('name', 'API Dataset')
        description = body.get('description', '')
        items = body.get('items', [])
        
        if not items:
            return JsonResponse({'error': 'No items provided'}, status=400)
        
        cleaned_rows, errors, warnings = validate_dataset_rows(items)
        
        if errors:
            return JsonResponse({'errors': errors[:50], 'warnings': warnings[:20]}, status=400)
        
        with transaction.atomic():
            last_version = project.datasets.filter(name=name).order_by('-version').first()
            version = (last_version.version + 1) if last_version else 1
            
            dataset = Dataset.objects.create(
                project=project,
                name=name,
                version=version,
                description=description,
                file_name='api_ingest.json',
                row_count=len(cleaned_rows),
                created_by=request.user,
            )
            
            dataset_items = []
            for idx, cr in enumerate(cleaned_rows):
                dataset_items.append(DatasetItem(
                    dataset=dataset,
                    project=project,
                    task_id=cr['task_id'],
                    prompt=cr['prompt'],
                    context=cr['context'],
                    response_a=cr['response_a'],
                    response_b=cr['response_b'],
                    model_a=cr['model_a'],
                    model_b=cr['model_b'],
                    metadata=cr['metadata'],
                    reference_answer=cr['reference_answer'],
                    order_index=idx,
                    content_hash=cr['content_hash'],
                ))
            DatasetItem.objects.bulk_create(dataset_items, batch_size=500)
        
        log_audit(request, 'dataset_api_ingested', project, details={'dataset_id': dataset.id, 'count': len(cleaned_rows)})
        
        return JsonResponse({
            'success': True,
            'dataset_id': dataset.id,
            'version': version,
            'row_count': len(cleaned_rows),
            'warnings': warnings[:20]
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def api_report(request, project_pk):
    """Retrieve analytics report via API"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    project = get_object_or_404(Project, pk=project_pk)
    if not project.can_view_analytics(request.user):
        return HttpResponseForbidden("No permission")
    
    from apps.analytics.services import analytics_summary
    from apps.evaluations.models import Review, Assignment, Issue
    
    reviews_qs = project.reviews.all()
    assignments_qs = project.assignments.all()
    issues_qs = project.issues.all()
    
    summary = analytics_summary(project, reviews_qs, assignments_qs, issues_qs)
    
    return JsonResponse({
        'project': {
            'id': project.id,
            'name': project.name,
            'task_type': project.task_type,
        },
        'summary': summary,
    })

@login_required
def api_autosave(request, assignment_pk):
    """Autosave draft review - HTMX endpoint"""
    from apps.evaluations.models import Assignment, Review, ReviewDimensionScore
    from apps.rubrics.models import Rubric
    from django.utils import timezone
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    assignment = get_object_or_404(Assignment, pk=assignment_pk)
    if assignment.reviewer != request.user:
        return HttpResponseForbidden("Not authorized")
    
    project = assignment.project
    rubric = project.rubrics.filter(is_active=True).order_by('-version').first()
    if not rubric:
        return JsonResponse({'error': 'No active rubric'}, status=400)
    
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST.dict()
        
        # Extract fields
        preference = data.get('preference', '')
        confidence = data.get('confidence', 3)
        rationale = data.get('rationale', '')
        time_spent = data.get('time_spent_seconds', 0)
        
        # Validate preference
        if preference and preference not in ['response_a', 'response_b', 'tie', 'both_bad']:
            return JsonResponse({'error': 'Invalid preference'}, status=400)
        
        with transaction.atomic():
            try:
                review = assignment.review
            except Review.DoesNotExist:
                review = None
            
            # Determine original preference
            if preference:
                original_pref = assignment.dataset_item.get_original_label_for_display(preference, assignment.display_a_is_original_a)
            else:
                original_pref = 'tie'
            
            if review:
                if preference:
                    review.preference = original_pref
                    review.display_preference = preference
                if confidence:
                    try:
                        review.confidence = int(confidence)
                    except:
                        pass
                if rationale is not None:
                    review.rationale = rationale
                review.is_draft = True
                review.time_spent_seconds = int(time_spent) if str(time_spent).isdigit() else review.time_spent_seconds
                review.save()
                
                # Handle dimension scores if provided
                # Expect format: dim_<id>_a, dim_<id>_b
                review.dimension_scores.all().delete()
                for dim in rubric.dimensions.all():
                    score_a_key = f'dim_{dim.id}_a'
                    score_b_key = f'dim_{dim.id}_b'
                    na_key = f'dim_{dim.id}_na'
                    
                    is_na = data.get(na_key) in ['true', 'on', '1', True]
                    score_a = data.get(score_a_key)
                    score_b = data.get(score_b_key)
                    
                    try:
                        score_a = int(score_a) if score_a not in [None, ''] else None
                    except:
                        score_a = None
                    try:
                        score_b = int(score_b) if score_b not in [None, ''] else None
                    except:
                        score_b = None
                    
                    if is_na or score_a is not None or score_b is not None:
                        ReviewDimensionScore.objects.create(
                            review=review,
                            dimension=dim,
                            score_a=score_a,
                            score_b=score_b,
                            is_na=is_na
                        )
            else:
                # Create draft review
                review = Review.objects.create(
                    assignment=assignment,
                    project=project,
                    dataset_item=assignment.dataset_item,
                    reviewer=assignment.reviewer,
                    rubric=rubric,
                    preference=original_pref if preference else 'tie',
                    display_preference=preference if preference else 'tie',
                    confidence=int(confidence) if str(confidence).isdigit() else 3,
                    rationale=rationale,
                    is_draft=True,
                    display_a_is_original_a=assignment.display_a_is_original_a,
                    time_spent_seconds=int(time_spent) if str(time_spent).isdigit() else 0,
                )
            
            # Update assignment status
            if assignment.status == 'pending':
                assignment.status = 'in_progress'
                assignment.save(update_fields=['status', 'updated_at'])
        
        return JsonResponse({'status': 'draft_saved', 'review_id': review.id, 'timestamp': timezone.now().isoformat()})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
