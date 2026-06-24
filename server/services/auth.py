from __future__ import annotations

import sqlite3

from server import config
from server.database import row
from server.security import expires_iso, hash_password, now_iso, token, verify_password


PUBLIC_USER_FIELDS = "id, email, name, role, created_at"


def user_public(user: dict) -> dict:
    return {key: user[key] for key in ("id", "email", "name", "role", "created_at")}


def register(conn: sqlite3.Connection, email: str, name: str, password: str) -> dict:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters.")
    try:
        cur = conn.execute(
            "INSERT INTO users(email, name, password_hash, role, created_at) VALUES (?, ?, ?, 'member', ?)",
            (email.lower().strip(), name.strip(), hash_password(password), now_iso()),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("An account already exists for that email.") from exc
    return user_public(row(conn, f"SELECT {PUBLIC_USER_FIELDS} FROM users WHERE id = ?", (cur.lastrowid,)))


def login(conn: sqlite3.Connection, email: str, password: str) -> tuple[dict, dict]:
    user = row(conn, "SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    if not user or not verify_password(password, user["password_hash"]):
        raise ValueError("Invalid email or password.")
    session_id = token()
    csrf = token()
    conn.execute(
        "INSERT INTO sessions(id, user_id, csrf_token, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, user["id"], csrf, expires_iso(), now_iso()),
    )
    return user_public(user), {"id": session_id, "csrf": csrf}


def logout(conn: sqlite3.Connection, session_id: str | None) -> None:
    if session_id:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def current_user(conn: sqlite3.Connection, session_id: str | None) -> tuple[dict | None, dict | None]:
    if not session_id:
        return None, None
    session = row(conn, "SELECT * FROM sessions WHERE id = ? AND expires_at > ?", (session_id, now_iso()))
    if not session:
        return None, None
    user = row(conn, f"SELECT {PUBLIC_USER_FIELDS} FROM users WHERE id = ?", (session["user_id"],))
    return user, session


def session_cookie(session_id: str) -> str:
    return f"{config.SESSION_COOKIE}={session_id}; HttpOnly; SameSite=Lax; Path=/; Max-Age={config.SESSION_DAYS * 86400}"


def clear_cookie() -> str:
    return f"{config.SESSION_COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"

