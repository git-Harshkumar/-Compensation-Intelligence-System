from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from server import config
from server.database import connect, migrate
from server.db.seed import seed
from server.services import auth, compensation


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        self.status = status
        self.message = message


class Handler(BaseHTTPRequestHandler):
    server_version = "LevelLens/1.0"

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        self.route()

    def do_POST(self) -> None:
        self.route()

    def route(self) -> None:
        try:
            path = urlparse(self.path).path
            if path.startswith("/api/"):
                self.handle_api(path)
            else:
                self.serve_static(path)
        except ApiError as exc:
            self.json_response({"error": exc.message}, exc.status)
        except Exception as exc:
            self.json_response({"error": "Unexpected server error.", "detail": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def read_json(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Request body must be valid JSON.") from exc

    def cookie_session(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("cookie"))
        morsel = cookie.get(config.SESSION_COOKIE)
        return morsel.value if morsel else None

    def require_user(self, conn) -> tuple[dict, dict]:
        user, session = auth.current_user(conn, self.cookie_session())
        if not user or not session:
            raise ApiError(HTTPStatus.UNAUTHORIZED, "Authentication required.")
        if self.command in {"POST", "PUT", "PATCH", "DELETE"}:
            provided = self.headers.get(config.CSRF_HEADER)
            if provided != session["csrf_token"]:
                raise ApiError(HTTPStatus.FORBIDDEN, "Invalid CSRF token.")
        return user, session

    def handle_api(self, path: str) -> None:
        with connect() as conn:
            if self.command == "GET" and path == "/api/health":
                self.json_response({"ok": True, "service": "levellens"})
                return

            if self.command == "POST" and path == "/api/auth/register":
                payload = self.read_json()
                user = auth.register(conn, payload.get("email", ""), payload.get("name", ""), payload.get("password", ""))
                self.json_response({"user": user}, HTTPStatus.CREATED)
                return

            if self.command == "POST" and path == "/api/auth/login":
                payload = self.read_json()
                user, session = auth.login(conn, payload.get("email", ""), payload.get("password", ""))
                self.json_response({"user": user, "csrfToken": session["csrf"]}, headers={"Set-Cookie": auth.session_cookie(session["id"])})
                return

            if self.command == "POST" and path == "/api/auth/logout":
                auth.logout(conn, self.cookie_session())
                self.json_response({"ok": True}, headers={"Set-Cookie": auth.clear_cookie()})
                return

            if self.command == "GET" and path == "/api/me":
                user, session = auth.current_user(conn, self.cookie_session())
                self.json_response({"user": user, "csrfToken": session["csrf_token"] if session else None})
                return

            if self.command == "GET" and path == "/api/reference":
                self.require_user(conn)
                self.json_response(compensation.reference_data(conn))
                return

            if self.command == "GET" and path == "/api/benchmarks":
                self.require_user(conn)
                query = {key: values[0] for key, values in parse_qs(urlparse(self.path).query).items()}
                self.json_response(compensation.benchmark(conn, query))
                return

            if self.command == "POST" and path == "/api/compare":
                self.require_user(conn)
                payload = self.read_json()
                self.json_response(compensation.compare(conn, payload.get("cohorts", [])))
                return

            if self.command == "GET" and path == "/api/levels/matrix":
                self.require_user(conn)
                query = {key: values[0] for key, values in parse_qs(urlparse(self.path).query).items()}
                self.json_response(compensation.level_matrix(conn, query.get("role", ""), query.get("location", "")))
                return

            if self.command == "GET" and path == "/api/locations/adjustment":
                self.require_user(conn)
                query = {key: values[0] for key, values in parse_qs(urlparse(self.path).query).items()}
                self.json_response(compensation.location_adjustment(conn, query.get("role", ""), query.get("level", "")))
                return

            if self.command == "GET" and path == "/api/structure":
                self.require_user(conn)
                query = {key: values[0] for key, values in parse_qs(urlparse(self.path).query).items()}
                self.json_response(
                    compensation.structure_insights(
                        conn,
                        query.get("role", ""),
                        query.get("level", ""),
                        query.get("location", ""),
                    )
                )
                return

            if self.command == "GET" and path == "/api/submissions":
                user, _ = self.require_user(conn)
                self.json_response({"submissions": compensation.submissions_for_user(conn, user["id"])})
                return

            if self.command == "POST" and path == "/api/submissions":
                user, _ = self.require_user(conn)
                self.json_response(compensation.submit_compensation(conn, user["id"], self.read_json()), HTTPStatus.CREATED)
                return

        raise ApiError(HTTPStatus.NOT_FOUND, "Route not found.")

    def serve_static(self, path: str) -> None:
        requested = "index.html" if path in {"", "/"} else path.lstrip("/")
        file_path = (config.WEB_DIR / requested).resolve()
        if not str(file_path).startswith(str(config.WEB_DIR.resolve())) or not file_path.exists() or file_path.is_dir():
            file_path = config.WEB_DIR / "index.html"
        body = file_path.read_bytes()
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, payload: dict, status: HTTPStatus = HTTPStatus.OK, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    migrate()
    seed()
    server = ThreadingHTTPServer((config.APP_HOST, config.APP_PORT), Handler)
    print(f"LevelLens running at http://{config.APP_HOST}:{config.APP_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
