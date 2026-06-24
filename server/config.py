from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = Path(os.environ.get("LEVELLENS_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("LEVELLENS_DB_PATH", DATA_DIR / "levellens.sqlite3"))

APP_HOST = os.environ.get("LEVELLENS_HOST", "127.0.0.1")
APP_PORT = int(os.environ.get("LEVELLENS_PORT", "8000"))
SESSION_COOKIE = "levellens_session"
CSRF_HEADER = "x-csrf-token"
SESSION_DAYS = int(os.environ.get("LEVELLENS_SESSION_DAYS", "7"))

