# Troubleshooting

## Common Issues

### Migrations fail
```bash
python manage.py migrate --run-syncdb
# If still fails, delete db.sqlite3 and re-migrate (dev only)
rm db.sqlite3
python manage.py migrate
python manage.py seed_demo
```

### No active rubric error when reviewing
- Create a rubric for the project: Project Detail -> Rubrics -> Create Rubric -> Use defaults
- Ensure rubric is marked active (default)

### Assignment not showing in queue
- Check assignment reviewer matches logged-in user
- Check status is pending/in_progress
- Ensure project membership exists

### Import fails: missing required columns
- CSV must have header row with at least prompt, response_a, response_b
- Check file encoding UTF-8
- Max 10MB

### Kappa undefined
- Need at least 2 reviewers rating same items
- Need at least 2 categories present (not all same preference)
- Need paired observations (same item reviewed by both)
- Check "No paired items" message - create double assignments

### Permission denied
- Ensure user is member of project
- Manager role required for: project edit, dataset upload, rubric edit, assignment creation, adjudication, analytics
- Reviewer role can only review own assignments
- Observer can only view analytics

### Static files not loading
```bash
python manage.py collectstatic --noinput
```

### Playwright tests fail
- Install browsers: `playwright install`
- Skip e2e tests if not needed: `pytest -k "not e2e"`

### Docker build fails
- Ensure Docker daemon running
- Check Dockerfile uses python:3.11-slim, build-essential installed
- Try `docker-compose down -v` then up

### Seed command creates duplicate data
- Seed is idempotent for users, projects, datasets, rubrics (get_or_create)
- But assignments/reviews may duplicate if run multiple times - it uses get_or_create for assignments, but skips review creation if exists
- To reset: delete db.sqlite3 and re-seed

### Login fails after seed
- Passwords are reset on each seed to env defaults
- Check .env.example for defaults
- Try admin / AdminPass123!

### Blind review shows model names
- Blind review only hides for reviewer (not manager)
- Check project.blind_review = True
- Manager viewing review_workspace will still see model names (to allow adjudication)

### Other reviews visible before submission
- Bug: should only show other reviews after own submission or if manager
- Check view logic: can_view_others = project.can_edit(user) or (existing_review and not is_draft)
- Ensure you submitted your review first

## Logs
- Django logs to console
- Check `python manage.py runserver` output
- AuditLog in project detail shows actions

## Getting Help
- Check docs/architecture.md, docs/evaluation-methodology.md
- Open issue with steps to reproduce, logs, and screenshots
