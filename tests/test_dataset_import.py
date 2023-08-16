import pytest
from apps.datasets.services import parse_file_content, validate_dataset_rows

def test_parse_csv_valid():
    csv_content = "task_id,prompt,response_a,response_b\n1,What is 2+2?,4,Four\n"
    rows = parse_file_content(csv_content, 'csv')
    assert len(rows) == 1
    assert rows[0]['prompt'] == 'What is 2+2?'

def test_parse_csv_missing_required():
    csv_content = "task_id,prompt\n1,Only prompt\n"
    try:
        rows = parse_file_content(csv_content, 'csv')
        assert False, "Should have raised ValidationError"
    except Exception as e:
        assert 'missing required' in str(e).lower()

def test_parse_json():
    json_content = '[{"task_id": "1", "prompt": "Q", "response_a": "A", "response_b": "B"}]'
    rows = parse_file_content(json_content, 'json')
    assert len(rows) == 1

def test_parse_jsonl():
    jsonl_content = '{"task_id": "1", "prompt": "Q", "response_a": "A", "response_b": "B"}\n{"task_id": "2", "prompt": "Q2", "response_a": "A2", "response_b": "B2"}'
    rows = parse_file_content(jsonl_content, 'jsonl')
    assert len(rows) == 2

def test_validate_rows():
    raw = [
        {'task_id': '1', 'prompt': 'What is capital?', 'response_a': 'Paris', 'response_b': 'Lyon'},
        {'task_id': '2', 'prompt': 'Short', 'response_a': '', 'response_b': 'B'},  # invalid
    ]
    cleaned, errors, warnings = validate_dataset_rows(raw)
    assert len(cleaned) == 1
    assert len(errors) >= 1

def test_duplicate_detection():
    raw = [
        {'task_id': '1', 'prompt': 'Same prompt', 'response_a': 'A', 'response_b': 'B'},
        {'task_id': '1', 'prompt': 'Same prompt', 'response_a': 'A', 'response_b': 'B'},
    ]
    cleaned, errors, warnings = validate_dataset_rows(raw)
    assert len(warnings) >= 1  # duplicate task_id
