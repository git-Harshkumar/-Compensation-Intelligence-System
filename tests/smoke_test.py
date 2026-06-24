from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib import request
from urllib.error import HTTPError


class SmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["LEVELLENS_DATA_DIR"] = cls.temp_dir.name
        os.environ["LEVELLENS_DB_PATH"] = os.path.join(cls.temp_dir.name, "test.sqlite3")
        from server.app import Handler
        from server.database import migrate
        from server.db.seed import seed

        migrate()
        seed()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_port
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        time.sleep(0.1)
        cls.temp_dir.cleanup()

    def call(self, path, method="GET", payload=None, headers=None):
        body = json.dumps(payload).encode() if payload is not None else None
        req = request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        with request.urlopen(req) as response:
            return response, json.loads(response.read().decode())

    def login(self):
        response, payload = self.call(
            "/api/auth/login",
            "POST",
            {"email": "demo@levellens.local", "password": "demo-password"},
        )
        cookie = SimpleCookie(response.headers["Set-Cookie"])
        return cookie["levellens_session"].value, payload["csrfToken"]

    def test_health(self):
        _, payload = self.call("/api/health")
        self.assertTrue(payload["ok"])

    def test_auth_and_benchmark(self):
        session_id, csrf = self.login()
        headers = {"Cookie": f"levellens_session={session_id}", "x-csrf-token": csrf}
        _, payload = self.call("/api/benchmarks?role=software-engineering&level=L5&location=remote-us", headers=headers)
        self.assertGreater(payload["summary"]["median"], 0)
        self.assertGreaterEqual(payload["summary"]["count"], 5)

    def test_comparison(self):
        session_id, csrf = self.login()
        headers = {"Cookie": f"levellens_session={session_id}", "x-csrf-token": csrf}
        _, payload = self.call(
            "/api/compare",
            "POST",
            {
                "cohorts": [
                    {"role": "software-engineering", "level": "L5", "location": "remote-us"},
                    {"role": "software-engineering", "level": "L6", "location": "remote-us"},
                ]
            },
            headers,
        )
        self.assertEqual(len(payload["cohorts"]), 2)
        self.assertGreater(payload["cohorts"][1]["deltaFromBaseline"], 0)

    def test_intelligence_workflows(self):
        session_id, csrf = self.login()
        headers = {"Cookie": f"levellens_session={session_id}", "x-csrf-token": csrf}

        _, levels = self.call("/api/levels/matrix?role=software-engineering&location=remote-us", headers=headers)
        self.assertEqual(len(levels["levels"]), 5)
        self.assertGreater(levels["levels"][-1]["summary"]["median"], levels["levels"][0]["summary"]["median"])

        _, locations = self.call("/api/locations/adjustment?role=software-engineering&level=L5", headers=headers)
        self.assertGreaterEqual(len(locations["locations"]), 5)

        _, structure = self.call("/api/structure?role=software-engineering&level=L5&location=remote-us", headers=headers)
        self.assertGreater(structure["summary"]["baseShare"], 0)
        self.assertGreater(len(structure["mixes"]), 0)

    def test_requires_auth(self):
        with self.assertRaises(HTTPError) as raised:
            self.call("/api/reference")
        self.assertEqual(raised.exception.code, 401)


if __name__ == "__main__":
    unittest.main()
