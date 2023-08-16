from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.db.models import Count
from apps.projects.models import Project
from apps.evaluations.models import Review, Assignment, Issue, PreferenceChoice
from .services import compute_cohen_kappa, compute_fleiss_kappa, analytics_summary, paired_reviews_for_kappa
import json
import pandas as pd

@login_required
def analytics_dashboard(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.can_view_analytics(request.user):
        return HttpResponseForbidden("No permission to view analytics")

    reviews_qs = project.reviews.all()
    assignments_qs = project.assignments.all()
    issues_qs = project.issues.all()

    # Filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    reviewer_id = request.GET.get('reviewer')

    if reviewer_id:
        reviews_qs = reviews_qs.filter(reviewer_id=reviewer_id)
        issues_qs = issues_qs.filter(reviewer_id=reviewer_id)

    # Summary
    summary = analytics_summary(project, reviews_qs, assignments_qs, issues_qs)

    # Kappa calculations
    # Overall kappa if double reviewed
    paired = paired_reviews_for_kappa(project)
    kappa_result = None
    if paired:
        prefs1 = [p[1] for p in paired]
        prefs2 = [p[2] for p in paired]
        kappa_result = compute_cohen_kappa(prefs1, prefs2)
        kappa_result['paired_items'] = paired[:20]  # sample
        kappa_result['total_paired'] = len(paired)

    # Per-reviewer pair kappa
    # Find all reviewer pairs that have overlapping items
    from collections import defaultdict
    from django.contrib.auth.models import User

    # Get reviewer pairs
    reviewer_pairs = []
    reviewers = User.objects.filter(reviews__project=project, reviews__is_draft=False).distinct()
    reviewers_list = list(reviewers)

    pair_kappas = []
    for i in range(len(reviewers_list)):
        for j in range(i+1, len(reviewers_list)):
            r1 = reviewers_list[i]
            r2 = reviewers_list[j]
            paired_specific = paired_reviews_for_kappa(project, reviewer1_id=r1.id, reviewer2_id=r2.id)
            if len(paired_specific) >= 2:
                prefs1 = [p[1] for p in paired_specific]
                prefs2 = [p[2] for p in paired_specific]
                k_res = compute_cohen_kappa(prefs1, prefs2)
                pair_kappas.append({
                    'reviewer1': r1.username,
                    'reviewer2': r2.username,
                    'kappa': k_res['kappa'],
                    'percent_agreement': k_res['percent_agreement'],
                    'n': k_res['n'],
                    'error': k_res['error'],
                })

    # For Fleiss if >2 reviewers per item
    fleiss_result = None
    # Build matrix for Fleiss: need counts per category per item
    # Let's build for items with >=2 reviewers
    from apps.datasets.models import DatasetItem
    items = project.dataset_items.filter(is_active=True)
    fleiss_matrix = []
    categories = ['response_a', 'response_b', 'tie', 'both_bad']
    cat_index = {c: i for i, c in enumerate(categories)}
    for item in items:
        revs = item.reviews.filter(is_draft=False)
        if revs.count() >= 2:
            counts = [0]*len(categories)
            for r in revs:
                if r.preference in cat_index:
                    counts[cat_index[r.preference]] += 1
            # Only include if sum >=2
            if sum(counts) >= 2:
                fleiss_matrix.append(counts)
    if len(fleiss_matrix) >= 2 and len(reviewers_list) > 2:
        fleiss_result = compute_fleiss_kappa(fleiss_matrix)
        fleiss_result['categories'] = categories

    # Plotly charts data (we'll generate JSON for frontend)
    # Preference distribution pie
    pref_labels = list(summary['pref_counts'].keys())
    pref_values = list(summary['pref_counts'].values())

    # Dimension averages bar
    dim_names = [d['dimension'] for d in summary['dim_summary']]
    dim_avg_a = [d['avg_a'] or 0 for d in summary['dim_summary']]
    dim_avg_b = [d['avg_b'] or 0 for d in summary['dim_summary']]

    context = {
        'project': project,
        'summary': summary,
        'kappa_result': kappa_result,
        'pair_kappas': pair_kappas,
        'fleiss_result': fleiss_result,
        'reviewers': reviewers_list,
        'pref_labels_json': json.dumps(pref_labels),
        'pref_values_json': json.dumps(pref_values),
        'dim_names_json': json.dumps(dim_names),
        'dim_avg_a_json': json.dumps(dim_avg_a),
        'dim_avg_b_json': json.dumps(dim_avg_b),
        'filter_reviewer': reviewer_id,
    }
    return render(request, 'analytics/dashboard.html', context)

@login_required
def calibration_view(request, project_pk):
    """Reviewer calibration examples with known reference labels"""
    project = get_object_or_404(Project, pk=project_pk)
    if not project.is_member(request.user):
        return HttpResponseForbidden("Not member")
    
    # Calibration examples: items with reference answers and known good preference
    # For demo, we use items where reference answer exists and we have a known correct preference
    calibration_items = project.dataset_items.filter(is_active=True).exclude(reference_answer='').order_by('task_id')[:10]
    
    # Known reference labels (hardcoded for demo, in real would be from expert)
    reference_labels = {
        'qa_001': {'preference': 'response_a', 'reason': 'Paris is correct per reference', 'factual_accuracy': {'a': 5, 'b': 1}},
        'qa_002': {'preference': 'response_a', 'reason': 'A correctly notes no FTL communication', 'factual_accuracy': {'a': 5, 'b': 2}},
        'qa_003': {'preference': 'response_a', 'reason': 'Jane Austen 1813 per reference', 'factual_accuracy': {'a': 5, 'b': 1}},
        'code_001': {'preference': 'response_a', 'reason': 'A handles edge cases and is efficient O(sqrt(n))', 'completeness': {'a': 5, 'b': 2}},
        'code_002': {'preference': 'response_a', 'reason': 'A is binary search O(log n), B is linear', 'completeness': {'a': 5, 'b': 2}},
    }
    
    return render(request, 'analytics/calibration.html', {
        'project': project,
        'calibration_items': calibration_items,
        'reference_labels': reference_labels,
    })

@login_required
def anonymized_export(request, project_pk):
    """Optional anonymized project export - removes PII, keeps evaluation data"""
    project = get_object_or_404(Project, pk=project_pk)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("Only managers can export anonymized data")
    
    import hashlib
    
    reviews_qs = project.reviews.filter(is_draft=False).select_related('dataset_item', 'rubric').prefetch_related('dimension_scores__dimension', 'issues')
    
    # Anonymize reviewer usernames via hashing
    def anonymize(username):
        return 'reviewer_' + hashlib.sha256(username.encode()).hexdigest()[:8]
    
    data = {
        'project': {
            'name': project.name,
            'task_type': project.task_type,
            'description': project.description,
            'goal': project.goal,
            'blind_review': project.blind_review,
        },
        'rubrics': [
            {
                'name': r.name,
                'version': r.version,
                'dimensions': [
                    {'key': d.key, 'name': d.name, 'scale': f"{d.scale_min}-{d.scale_max}", 'weight': d.weight}
                    for d in r.dimensions.all()
                ]
            }
            for r in project.rubrics.all()
        ],
        'reviews': []
    }
    
    for r in reviews_qs:
        data['reviews'].append({
            'task_id': r.dataset_item.task_id,
            'prompt': r.dataset_item.prompt,
            'response_a': r.dataset_item.response_a,
            'response_b': r.dataset_item.response_b,
            'model_a': r.dataset_item.model_a,
            'model_b': r.dataset_item.model_b,
            'reviewer': anonymize(r.reviewer.username),
            'preference': r.preference,
            'confidence': r.confidence,
            'rationale': r.rationale,
            'rubric_version': r.rubric.version,
            'dimension_scores': [
                {'dimension': ds.dimension.key, 'score_a': ds.score_a, 'score_b': ds.score_b, 'is_na': ds.is_na}
                for ds in r.dimension_scores.all()
            ],
            'issues': [
                {'response_target': iss.response_target, 'category': iss.category, 'severity': iss.severity}
                for iss in r.issues.all()
            ],
            'submitted_at': r.submitted_at.isoformat() if r.submitted_at else None,
        })
    
    response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{project.name}_anonymized.json"'
    return response

@login_required
def export_report(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.can_view_analytics(request.user):
        return HttpResponseForbidden("No permission")

    fmt = request.GET.get('format', 'json')
    reviews_qs = project.reviews.filter(is_draft=False).select_related('reviewer', 'dataset_item', 'rubric').prefetch_related('dimension_scores__dimension', 'issues')

    if fmt == 'csv':
        import csv
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{project.name}_reviews.csv"'
        writer = csv.writer(response)
        writer.writerow(['task_id', 'prompt', 'response_a', 'response_b', 'model_a', 'model_b', 'reviewer', 'preference', 'confidence', 'rationale', 'rubric_version', 'submitted_at'])
        for r in reviews_qs:
            writer.writerow([
                r.dataset_item.task_id,
                r.dataset_item.prompt[:500],
                r.dataset_item.response_a[:500],
                r.dataset_item.response_b[:500],
                r.dataset_item.model_a,
                r.dataset_item.model_b,
                r.reviewer.username,
                r.preference,
                r.confidence,
                r.rationale[:1000],
                r.rubric.version,
                r.submitted_at,
            ])
        return response
    elif fmt == 'jsonl':
        response = HttpResponse(content_type='application/jsonl')
        response['Content-Disposition'] = f'attachment; filename="{project.name}_reviews.jsonl"'
        for r in reviews_qs:
            obj = {
                'task_id': r.dataset_item.task_id,
                'prompt': r.dataset_item.prompt,
                'response_a': r.dataset_item.response_a,
                'response_b': r.dataset_item.response_b,
                'model_a': r.dataset_item.model_a,
                'model_b': r.dataset_item.model_b,
                'reviewer': r.reviewer.username,
                'preference': r.preference,
                'display_preference': r.display_preference,
                'confidence': r.confidence,
                'rationale': r.rationale,
                'rubric_version': r.rubric.version,
                'dimension_scores': [
                    {
                        'dimension': ds.dimension.key,
                        'score_a': ds.score_a,
                        'score_b': ds.score_b,
                        'is_na': ds.is_na
                    } for ds in r.dimension_scores.all()
                ],
                'issues': [
                    {
                        'response_target': iss.response_target,
                        'category': iss.category,
                        'severity': iss.severity,
                        'excerpt': iss.excerpt,
                        'explanation': iss.explanation
                    } for iss in r.issues.all()
                ],
                'submitted_at': r.submitted_at.isoformat() if r.submitted_at else None,
            }
            response.write(json.dumps(obj) + "\n")
        return response
    else:
        # JSON
        data = []
        for r in reviews_qs:
            data.append({
                'task_id': r.dataset_item.task_id,
                'prompt': r.dataset_item.prompt,
                'response_a': r.dataset_item.response_a,
                'response_b': r.dataset_item.response_b,
                'model_a': r.dataset_item.model_a,
                'model_b': r.dataset_item.model_b,
                'reviewer': r.reviewer.username,
                'preference': r.preference,
                'confidence': r.confidence,
                'rationale': r.rationale,
                'rubric_version': r.rubric.version,
                'submitted_at': r.submitted_at.isoformat() if r.submitted_at else None,
            })
        response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{project.name}_reviews.json"'
        return response
