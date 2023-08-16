# Deployment Guide

## Local Development (SQLite)

### Prerequisites
- Python 3.11+
- pip

### Setup
```bash
git clone <repo>
cd human-feedback-ai-grader
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\Activate.ps1 on Windows

pip install -r requirements.txt
cp .env.example .env
# Edit .env if needed

python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Access at http://localhost:8000

Demo accounts:
- admin / AdminPass123!
- manager / ManagerPass123!
- reviewer1 / ReviewerPass123!
- reviewer2 / ReviewerPass123!
- observer / ObserverPass123!

## Docker (SQLite)

```bash
docker-compose up --build
```

This will:
- Build image
- Run migrations
- Seed demo data
- Start Gunicorn on port 8000

Access at http://localhost:8000

Shutdown:
```bash
docker-compose down
```

## Docker with PostgreSQL

```bash
docker-compose --profile postgres up --build
```

Set DATABASE_URL in .env:
```
DATABASE_URL=postgres://postgres:postgres@db:5432/human_feedback
```

## Production Considerations

### Environment Variables
- SECRET_KEY: generate random 50+ chars, e.g., `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- DEBUG=False
- ALLOWED_HOSTS=yourdomain.com
- DATABASE_URL: postgres URL for production

### Security Checklist
- Set DEBUG=False
- Strong SECRET_KEY, not in repo
- ALLOWED_HOSTS restricted
- Use HTTPS (TLS termination via Nginx or Cloud Load Balancer)
- CSRF_COOKIE_SECURE=True, SESSION_COOKIE_SECURE=True (auto when DEBUG=False)
- Persistent database storage (volume)
- Regular backups
- Audit logs reviewed
- No secrets in logs or screenshots

### Static Files
- WhiteNoise serves static in Docker
- For high traffic, use CDN or Nginx

### Gunicorn
Dockerfile uses:
```
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
```

Adjust workers = 2*CPU+1

### Health Checks
Dockerfile includes HEALTHCHECK that curls localhost:8000

### Database Backups
SQLite: copy db.sqlite3
Postgres: pg_dump

## Troubleshooting
See docs/troubleshooting.md
