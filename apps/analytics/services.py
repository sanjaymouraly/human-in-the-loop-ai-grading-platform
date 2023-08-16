from typing import List, Dict, Tuple, Optional
import pandas as pd
import numpy as np
from sklearn.metrics import cohen_kappa_score, confusion_matrix
from collections import Counter, defaultdict

def compute_cohen_kappa(labels1: List[str], labels2: List[str], weights: Optional[str] = None) -> Dict:
    """
    Compute Cohen's kappa for two reviewers.
    Handles edge cases.
    """
    result = {
        'kappa': None,
        'percent_agreement': None,
        'n': len(labels1),
        'labels1_dist': dict(Counter(labels1)),
        'labels2_dist': dict(Counter(labels2)),
        'error': None,
        'confusion_matrix': None,
        'labels': None,
    }

    if len(labels1) == 0 or len(labels2) == 0:
        result['error'] = 'No paired observations'
        return result

    if len(labels1) != len(labels2):
        result['error'] = 'Mismatched lengths'
        return result

    # Percent agreement
    agreements = sum(1 for a, b in zip(labels1, labels2) if a == b)
    result['percent_agreement'] = agreements / len(labels1) if len(labels1) else None

    # Check single category
    all_labels = sorted(set(labels1 + labels2))
    result['labels'] = all_labels

    if len(all_labels) == 1:
        result['error'] = 'Only one category present - kappa undefined (perfect agreement but single label)'
        result['kappa'] = None
        # Still provide confusion matrix
        result['confusion_matrix'] = [[len(labels1)]]
        return result

    if len(all_labels) == 0:
        result['error'] = 'No labels'
        return result

    try:
        # Use sklearn
        kappa = cohen_kappa_score(labels1, labels2, weights=weights)
        result['kappa'] = float(kappa) if not np.isnan(kappa) else None
        if np.isnan(kappa):
            result['error'] = 'Kappa is NaN (possible zero division)'

        # Confusion matrix
        cm = confusion_matrix(labels1, labels2, labels=all_labels)
        result['confusion_matrix'] = cm.tolist()

    except Exception as e:
        result['error'] = str(e)
        result['kappa'] = None

    return result

def compute_fleiss_kappa(matrix: List[List[int]]) -> Dict:
    """
    Compute Fleiss' kappa for >2 reviewers.
    matrix: list of items, each item is list of counts per category
    Example: 3 categories, item rated by 3 reviewers: [1,2,0] means 1 vote for cat0, 2 for cat1, 0 for cat2
    """
    # Implementation based on standard formula
    if not matrix:
        return {'kappa': None, 'error': 'No data', 'n': 0}

    mat = np.array(matrix)
    n_items, n_categories = mat.shape
    n_raters_per_item = mat.sum(axis=1)

    # Check all same number of raters
    if len(set(n_raters_per_item)) != 1:
        return {'kappa': None, 'error': 'Different number of raters per item not supported for Fleiss', 'n': n_items}

    n = n_raters_per_item[0]
    if n < 2:
        return {'kappa': None, 'error': 'Need at least 2 raters per item', 'n': n_items}

    # Proportion of assignments to each category
    p_j = mat.sum(axis=0) / (n_items * n)
    # Proportion of agreement per item
    P_i = (np.sum(mat * (mat - 1), axis=1)) / (n * (n - 1))
    P_bar = np.mean(P_i)
    P_e_bar = np.sum(p_j ** 2)

    if P_e_bar == 1:
        kappa = 1.0 if P_bar == 1 else 0.0
    else:
        kappa = (P_bar - P_e_bar) / (1 - P_e_bar)

    return {
        'kappa': float(kappa),
        'P_bar': float(P_bar),
        'P_e_bar': float(P_e_bar),
        'n': n_items,
        'n_raters': int(n),
        'n_categories': int(n_categories),
        'error': None
    }

def analytics_summary(project, reviews_qs, assignments_qs, issues_qs):
    """
    Build summary stats for analytics dashboard
    """
    from apps.evaluations.models import PreferenceChoice

    total_items = project.dataset_items.filter(is_active=True).count()
    total_assignments = assignments_qs.count()
    total_reviews = reviews_qs.filter(is_draft=False).count()
    total_drafts = reviews_qs.filter(is_draft=True).count()

    # Preference distribution
    pref_counts = Counter(reviews_qs.filter(is_draft=False).values_list('preference', flat=True))

    # Model win rates - need to map original preference to model?
    # For simplicity, we report preference distribution
    # If we want model A vs B win, preference already is original A/B
    model_stats = {
        'response_a_wins': pref_counts.get('response_a', 0),
        'response_b_wins': pref_counts.get('response_b', 0),
        'ties': pref_counts.get('tie', 0),
        'both_bad': pref_counts.get('both_bad', 0),
    }

    # Reviewer productivity
    from django.db.models import Count as DjangoCount
    reviewer_productivity = list(
        reviews_qs.filter(is_draft=False)
        .values('reviewer__username', 'reviewer__id')
        .annotate(review_count=DjangoCount('id'))
        .order_by('-review_count')
    )

    # Issue categories
    issue_by_category = list(
        issues_qs.values('category').annotate(count=DjangoCount('id')).order_by('-count')
    )
    issue_by_severity = list(
        issues_qs.values('severity').annotate(count=DjangoCount('id')).order_by('-count')
    )

    # Average dimension scores
    from apps.evaluations.models import ReviewDimensionScore
    dim_scores = ReviewDimensionScore.objects.filter(review__in=reviews_qs.filter(is_draft=False)).select_related('dimension')
    dim_avg = defaultdict(list)
    dim_avg_a = defaultdict(list)
    dim_avg_b = defaultdict(list)
    for ds in dim_scores:
        if not ds.is_na:
            key = ds.dimension.name
            if ds.score_a is not None:
                dim_avg_a[key].append(ds.score_a)
            if ds.score_b is not None:
                dim_avg_b[key].append(ds.score_b)

    dim_summary = []
    for key in set(list(dim_avg_a.keys()) + list(dim_avg_b.keys())):
        scores_a = dim_avg_a.get(key, [])
        scores_b = dim_avg_b.get(key, [])
        dim_summary.append({
            'dimension': key,
            'avg_a': float(np.mean(scores_a)) if scores_a else None,
            'avg_b': float(np.mean(scores_b)) if scores_b else None,
            'count_a': len(scores_a),
            'count_b': len(scores_b),
        })

    # Completion
    completion_pct = (total_reviews / total_assignments * 100) if total_assignments else 0

    # Time spent
    time_spent = reviews_qs.filter(is_draft=False).exclude(time_spent_seconds=0).values_list('time_spent_seconds', flat=True)
    time_stats = {
        'avg': float(np.mean(list(time_spent))) if time_spent else None,
        'median': float(np.median(list(time_spent))) if time_spent else None,
        'min': int(min(time_spent)) if time_spent else None,
        'max': int(max(time_spent)) if time_spent else None,
    }

    return {
        'total_items': total_items,
        'total_assignments': total_assignments,
        'total_reviews': total_reviews,
        'total_drafts': total_drafts,
        'completion_pct': round(completion_pct, 1),
        'model_stats': model_stats,
        'pref_counts': dict(pref_counts),
        'reviewer_productivity': reviewer_productivity,
        'issue_by_category': issue_by_category,
        'issue_by_severity': issue_by_severity,
        'dim_summary': dim_summary,
        'time_stats': time_stats,
    }

def paired_reviews_for_kappa(project, reviewer1_id=None, reviewer2_id=None):
    """
    Get paired reviews for kappa calculation.
    Returns list of tuples (task_id, pref1, pref2)
    """
    from apps.evaluations.models import Review
    reviews = Review.objects.filter(project=project, is_draft=False).select_related('dataset_item', 'reviewer')

    # Group by dataset_item
    grouped = defaultdict(list)
    for r in reviews:
        grouped[r.dataset_item_id].append(r)

    paired = []
    for item_id, revs in grouped.items():
        if len(revs) < 2:
            continue
        # If specific reviewers requested
        if reviewer1_id and reviewer2_id:
            r1 = next((x for x in revs if x.reviewer_id == reviewer1_id), None)
            r2 = next((x for x in revs if x.reviewer_id == reviewer2_id), None)
            if r1 and r2:
                paired.append((r1.dataset_item.task_id, r1.preference, r2.preference, r1.reviewer.username, r2.reviewer.username))
        else:
            # Take first two for simple kappa, or all pairs?
            # For overall kappa, we need to consider all pairs or average?
            # We'll create all pairs for two-reviewer scenario, but for >2 we handle Fleiss separately
            # For simplicity, if exactly 2 reviewers per item, pair them
            if len(revs) == 2:
                paired.append((revs[0].dataset_item.task_id, revs[0].preference, revs[1].preference, revs[0].reviewer.username, revs[1].reviewer.username))

    return paired
