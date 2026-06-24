# LevelLens Compensation Intelligence

LevelLens is a compensation intelligence platform for structured, comparable salary data. It is intentionally not a job listing site. The core workflow helps users compare compensation by level, role family, location, and compensation structure, because levels matter more than job titles.

## What Is Included

- Frontend experience for login, benchmarks, comparisons, and submission review
- Backend APIs for authentication, datasets, submissions, and comparison workflows
- SQLite database with migrations and production-shaped schema
- Seeded compensation records for realistic local exploration
- Deployment assets for Docker and Compose
- Smoke tests for database, auth, and comparison behavior

## Quick Start

```powershell
python -m server.app
```

Then open:

```text
http://127.0.0.1:8000
```

Demo account:

```text
Email: demo@levellens.local
Password: demo-password
```

## Project Layout

```text
server/
  app.py                  HTTP server and route wiring
  config.py               Runtime settings
  database.py             SQLite connection and migration helpers
  security.py             Password hashing, sessions, CSRF helpers
  db/schema.sql           Database schema
  db/seed.py              Deterministic seed data
  services/
    auth.py               User and session workflows
    compensation.py       Benchmarks, comparisons, submissions
web/
  index.html              Product shell
  assets/app.js           Frontend state and API client
  assets/styles.css       UI system
deploy/
  Dockerfile
  docker-compose.yml
  .env.example
  DEPLOYMENT.md
tests/
  smoke_test.py
```

## Production Notes

The app is built to be dependency-light for reliability in constrained environments. It uses Python's standard library and SQLite. For larger production deployments, the service boundary is deliberately clean enough to replace SQLite with PostgreSQL and the session store with Redis without rewriting the product workflow.
