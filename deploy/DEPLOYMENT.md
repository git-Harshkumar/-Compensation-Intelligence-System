# Deployment

## Local Production Run

```powershell
$env:LEVELLENS_HOST="0.0.0.0"
$env:LEVELLENS_PORT="8000"
python -m server.app
```

## Docker Compose

```powershell
cd deploy
docker compose up --build
```

The service initializes the SQLite database on startup, applies migrations, and seeds demo data only when the database is empty.

## Operational Notes

- Persist `LEVELLENS_DATA_DIR` as a mounted volume.
- Terminate TLS at the platform load balancer or reverse proxy.
- Set secure cookie flags when serving exclusively over HTTPS.
- Move the database service behind the `server.database` module if replacing SQLite with PostgreSQL.
- Keep comparison logic in `server/services/compensation.py` so new compensation dimensions can be added without coupling them to route handlers.
