import pytest
from apps.analytics.services import compute_cohen_kappa, compute_fleiss_kappa

def test_cohen_kappa_perfect_agreement():
    labels1 = ['response_a', 'response_b', 'tie', 'response_a']
    labels2 = ['response_a', 'response_b', 'tie', 'response_a']
    result = compute_cohen_kappa(labels1, labels2)
    assert result['kappa'] == 1.0
    assert result['percent_agreement'] == 1.0

def test_cohen_kappa_no_agreement():
    labels1 = ['response_a', 'response_a', 'response_a']
    labels2 = ['response_b', 'response_b', 'response_b']
    result = compute_cohen_kappa(labels1, labels2)
    # With complete disagreement, kappa should be negative or zero
    assert result['percent_agreement'] == 0.0

def test_cohen_kappa_single_category():
    labels1 = ['response_a', 'response_a', 'response_a']
    labels2 = ['response_a', 'response_a', 'response_a']
    result = compute_cohen_kappa(labels1, labels2)
    assert result['kappa'] is None
    assert 'single category' in result['error'].lower() or 'only one' in result['error'].lower()

def test_cohen_kappa_no_paired():
    result = compute_cohen_kappa([], [])
    assert result['error'] is not None
    assert result['n'] == 0

def test_cohen_kappa_weighted():
    labels1 = [1, 2, 3, 4, 5]
    labels2 = [1, 2, 3, 4, 5]
    # Convert to strings for categorical
    result = compute_cohen_kappa([str(x) for x in labels1], [str(x) for x in labels2], weights='quadratic')
    assert result['kappa'] == 1.0

def test_fleiss_kappa():
    # 3 raters, 3 categories, 2 items
    # Item1: 2 raters say cat0, 1 says cat1
    # Item2: 1 rater cat0, 2 raters cat1
    matrix = [
        [2, 1, 0],
        [1, 2, 0],
    ]
    result = compute_fleiss_kappa(matrix)
    assert result['kappa'] is not None
    assert 'error' not in result or result['error'] is None

def test_fleiss_no_data():
    result = compute_fleiss_kappa([])
    assert result['kappa'] is None

def test_confusion_matrix():
    labels1 = ['a', 'b', 'a', 'b']
    labels2 = ['a', 'a', 'b', 'b']
    result = compute_cohen_kappa(labels1, labels2)
    assert result['confusion_matrix'] is not None
    assert len(result['confusion_matrix']) == 2
