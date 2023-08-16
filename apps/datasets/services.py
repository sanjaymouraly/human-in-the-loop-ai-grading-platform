import csv
import json
import io
import hashlib
from typing import List, Dict, Tuple
from django.core.exceptions import ValidationError

REQUIRED_FIELDS = ['prompt', 'response_a', 'response_b']
OPTIONAL_FIELDS = ['task_id', 'context', 'model_a', 'model_b', 'metadata', 'reference_answer']

def detect_format(filename: str, explicit: str):
    if explicit != 'auto':
        return explicit
    lower = filename.lower()
    if lower.endswith('.csv'):
        return 'csv'
    elif lower.endswith('.jsonl'):
        return 'jsonl'
    elif lower.endswith('.json'):
        return 'json'
    else:
        return 'csv'

def validate_row(row: Dict, index: int) -> Tuple[Dict, List[str]]:
    errors = []
    cleaned = {}

    # Normalize keys to lower
    normalized = {k.lower().strip(): v for k, v in row.items()}

    # Required
    for field in REQUIRED_FIELDS:
        if field not in normalized or not str(normalized[field]).strip():
            errors.append(f"Row {index}: Missing required field '{field}'")

    # task_id handling
    task_id = normalized.get('task_id') or normalized.get('id') or f"task_{index}"
    task_id = str(task_id).strip()
    if not task_id:
        errors.append(f"Row {index}: task_id empty")
    cleaned['task_id'] = task_id

    # Core fields
    cleaned['prompt'] = str(normalized.get('prompt', '')).strip()
    cleaned['response_a'] = str(normalized.get('response_a', '')).strip()
    cleaned['response_b'] = str(normalized.get('response_b', '')).strip()
    cleaned['context'] = str(normalized.get('context', '')).strip()
    cleaned['model_a'] = str(normalized.get('model_a', '')).strip()[:100]
    cleaned['model_b'] = str(normalized.get('model_b', '')).strip()[:100]
    cleaned['reference_answer'] = str(normalized.get('reference_answer', '') or normalized.get('reference', '')).strip()

    # metadata
    meta_raw = normalized.get('metadata', {})
    if isinstance(meta_raw, str):
        try:
            meta = json.loads(meta_raw) if meta_raw else {}
        except:
            meta = {'raw': meta_raw}
    elif isinstance(meta_raw, dict):
        meta = meta_raw
    else:
        meta = {}
    cleaned['metadata'] = meta

    # Additional validation: prompt length, response length
    if len(cleaned['prompt']) < 5:
        errors.append(f"Row {index}: prompt too short")
    if len(cleaned['response_a']) < 1 or len(cleaned['response_b']) < 1:
        errors.append(f"Row {index}: responses cannot be empty")

    # Hash for duplicate detection
    content = f"{cleaned['prompt']}|{cleaned['response_a']}|{cleaned['response_b']}"
    cleaned['content_hash'] = hashlib.sha256(content.encode('utf-8')).hexdigest()

    return cleaned, errors

def parse_csv(file_content: str) -> List[Dict]:
    f = io.StringIO(file_content)
    reader = csv.DictReader(f)
    if reader.fieldnames is None:
        raise ValidationError("CSV has no header row")
    # Normalize fieldnames check
    lower_fields = [h.lower().strip() for h in reader.fieldnames]
    missing = [rf for rf in REQUIRED_FIELDS if rf not in lower_fields]
    if missing:
        raise ValidationError(f"CSV missing required columns: {', '.join(missing)}. Found: {', '.join(reader.fieldnames)}")
    rows = list(reader)
    return rows

def parse_json(file_content: str) -> List[Dict]:
    try:
        data = json.loads(file_content)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON: {e}")
    if isinstance(data, dict):
        # Could be single object or have 'data' key
        if 'data' in data and isinstance(data['data'], list):
            return data['data']
        else:
            return [data]
    elif isinstance(data, list):
        return data
    else:
        raise ValidationError("JSON must be object or array of objects")

def parse_jsonl(file_content: str) -> List[Dict]:
    rows = []
    for i, line in enumerate(file_content.strip().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            rows.append(obj)
        except json.JSONDecodeError as e:
            raise ValidationError(f"JSONL line {i} invalid: {e}")
    return rows

def parse_file_content(content: str, fmt: str) -> List[Dict]:
    if fmt == 'csv':
        return parse_csv(content)
    elif fmt == 'json':
        return parse_json(content)
    elif fmt == 'jsonl':
        return parse_jsonl(content)
    else:
        raise ValidationError(f"Unsupported format {fmt}")

def validate_dataset_rows(raw_rows: List[Dict]) -> Tuple[List[Dict], List[str], List[str]]:
    """
    Returns cleaned_rows, errors, warnings
    """
    cleaned_rows = []
    errors = []
    warnings = []
    seen_task_ids = set()
    seen_hashes = set()

    for idx, raw in enumerate(raw_rows, 1):
        cleaned, row_errors = validate_row(raw, idx)
        if row_errors:
            errors.extend(row_errors)
            continue

        # Duplicate task_id within file
        if cleaned['task_id'] in seen_task_ids:
            warnings.append(f"Row {idx}: Duplicate task_id '{cleaned['task_id']}' within file")
        seen_task_ids.add(cleaned['task_id'])

        # Duplicate content hash
        if cleaned['content_hash'] in seen_hashes:
            warnings.append(f"Row {idx}: Duplicate content (same prompt+responses) as earlier row")
        seen_hashes.add(cleaned['content_hash'])

        cleaned_rows.append(cleaned)

    return cleaned_rows, errors, warnings
