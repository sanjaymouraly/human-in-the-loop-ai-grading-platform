# Contributing to Human Feedback AI Grader

Thank you for considering contributing!

## Development Setup

1. Fork and clone
2. Create venv: `python -m venv venv && source venv/bin/activate`
3. Install deps: `pip install -r requirements.txt`
4. Migrate: `python manage.py migrate`
5. Seed: `python manage.py seed_demo`
6. Run: `python manage.py runserver`

## Code Style

- Python-first, maintainable, beginner-intermediate friendly
- Use Django built-ins over excessive dependencies
- Follow PEP8, use `black` for formatting (non-blocking in CI)
- Write meaningful tests before considering feature complete

## Testing

```bash
pytest tests/test_auth_permissions.py tests/test_dataset_import.py tests/test_rubric.py tests/test_review_workflow.py tests/test_agreement.py -v
python manage.py check
```

## Pull Request Process

1. Create feature branch
2. Write tests for new functionality
3. Ensure all acceptance gates pass:
   - Fresh install starts
   - Auth and permissions work
   - Project creation, dataset import, rubric versioning, reviewer grading, issue reporting, multi-reviewer, disagreement adjudication, kappa stats, analytics, exports, tests
4. Update docs and README if needed
5. Ensure no secrets, private datasets, fake images, or placeholders remain (or document limitation honestly)
6. Submit PR with description of changes, tests executed, and screenshots if UI changed

## Security

- Do not include secrets in code, logs, or screenshots
- Report security issues privately
- Server-side authorization required, not just UI hiding
- Validate all uploads and inputs

## Evaluation Methodology

- Human judgments are source of truth
- No LLM auto-grading that undermines independent evaluation
- Preserve original judgments, never overwrite with adjudication
- Handle edge cases for kappa correctly, document exclusion rules
- Distinguish preference from factual correctness
