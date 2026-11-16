"""Fixtures + mock HTTP acceptance for scripts/ci_notify.py (no real network to Telegram).

Run: python scripts/test_ci_notify.py
"""

import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
NOTIFY = os.path.join(HERE, "ci_notify.py")
FIXTURES = os.path.join(HERE, "fixtures", "junit")

FAKE_TOKEN = "FAKE-TOKEN-123"
FAKE_CHAT = "-1009876543210"

BASE_ENV = {
    "PROJECT": "owner/getting-started-java",
    "WORKFLOW_NAME": "UI tests",
    "RUN_BRANCH": "vodin_homework",
    "RUN_SHA": "abcdef1234567890",
    "RUN_EVENT": "push",
    "RUN_URL": "https://github.com/owner/getting-started-java/actions/runs/42",
}


class MockTelegramHandler(BaseHTTPRequestHandler):
    server_version = "MockTelegram/1.0"

    def log_message(self, *args):
        pass

    def do_POST(self):
        server = self.server
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        server.requests.append((self.path, body))
        mode = server.mode
        if mode == "timeout":
            import time
            time.sleep(server.timeout_seconds)
            status, payload = 200, {"ok": True}
        elif mode == "http_500":
            status, payload = 500, {"ok": False, "description": "server error"}
        elif mode == "unauthorized":
            status, payload = 401, {"ok": False, "description": "Unauthorized"}
        elif mode == "ok_false":
            status, payload = 200, {"ok": False, "description": "chat not found"}
        else:
            status, payload = 200, {"ok": True, "result": {"message_id": 1}}
        raw = json.dumps(payload).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            self.server.aborted = getattr(self.server, "aborted", 0) + 1


class NotifyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockTelegramHandler)
        cls.server.mode = "ok"
        cls.server.requests = []
        cls.server.timeout_seconds = 0.5
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.api_base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    def setUp(self):
        self.server.requests.clear()
        self.server.mode = "ok"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def run_notify(self, result_dir, job_status="success", token=FAKE_TOKEN,
                   chat=FAKE_CHAT, timeout=None, extra=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("TELEGRAM")}
        env.update(BASE_ENV)
        env.update({
            "TELEGRAM_API_BASE": self.api_base,
            "TELEGRAM_BOT_TOKEN": token,
            "TELEGRAM_CHAT_ID": chat,
            "JOB_STATUS": job_status,
            "RESULT_DIR": result_dir,
            "PYTHONIOENCODING": "utf-8",
        })
        if timeout is not None:
            env["TELEGRAM_TIMEOUT"] = str(timeout)
        if extra:
            env.update(extra)
        proc = subprocess.run(
            [sys.executable, NOTIFY], env=env, cwd=HERE,
            capture_output=True, timeout=60,
        )
        stdout = proc.stdout.decode("utf-8", "replace")
        stderr = proc.stderr.decode("utf-8", "replace")
        return proc.returncode, stdout + stderr

    def sent_payload(self):
        self.assertEqual(len(self.server.requests), 1, "expected exactly one API call")
        path, body = self.server.requests[0]
        return path, json.loads(body.decode("utf-8"))

    def fixture(self, name):
        return os.path.join(FIXTURES, name)

    # 1
    def test_success(self):
        rc, out = self.run_notify(self.fixture("basic"))
        self.assertEqual(rc, 0)
        path, payload = self.sent_payload()
        self.assertIn("/bot" + FAKE_TOKEN + "/sendMessage", path)
        text = payload["text"]
        self.assertIn("\u2705", text)
        self.assertIn("passed 3 \u00b7 failed 0 \u00b7 errors 0 \u00b7 skipped 0 \u00b7 total 3", text)
        self.assertIn(BASE_ENV["RUN_URL"], text)
        self.assertIn("abcdef1", text)
        self.assertEqual(payload["chat_id"], FAKE_CHAT)
        self.assertIn("notify: sent", out)

    # 2
    def test_failure(self):
        rc, out = self.run_notify(self.fixture("failure"), job_status="failure")
        self.assertEqual(rc, 0)
        _, payload = self.sent_payload()
        self.assertIn("\u274c", payload["text"])
        self.assertIn("failed 1", payload["text"])
        self.assertIn("passed 2", payload["text"])

    # 3
    def test_errors_counted_separately(self):
        rc, _ = self.run_notify(self.fixture("error"), job_status="failure")
        self.assertEqual(rc, 0)
        _, payload = self.sent_payload()
        self.assertIn("errors 2", payload["text"])
        self.assertIn("failed 0", payload["text"])

    # 4
    def test_skipped(self):
        rc, _ = self.run_notify(self.fixture("skipped"))
        self.assertEqual(rc, 0)
        _, payload = self.sent_payload()
        self.assertIn("skipped 1 \u00b7 total 4", payload["text"])

    # 5
    def test_multi_file_sum(self):
        rc, _ = self.run_notify(self.fixture("multi"), job_status="failure")
        self.assertEqual(rc, 0)
        _, payload = self.sent_payload()
        self.assertIn("total 5", payload["text"])
        self.assertIn("failed 1", payload["text"])
        self.assertIn("skipped 1", payload["text"])

    # 6
    def test_testsuites_wrapper_not_double_counted(self):
        rc, _ = self.run_notify(self.fixture("nested"), job_status="failure")
        self.assertEqual(rc, 0)
        _, payload = self.sent_payload()
        self.assertIn("total 3", payload["text"])

    # 7
    def test_nested_inner_suites_counted_once(self):
        rc, _ = self.run_notify(self.fixture("nested_inner"))
        self.assertEqual(rc, 0)
        _, payload = self.sent_payload()
        self.assertIn("total 1", payload["text"])
        self.assertNotIn("total 9", payload["text"])
        self.assertIn("\u2705", payload["text"])

    # 8
    def test_broken_xml(self):
        rc, out = self.run_notify(self.fixture("broken"), job_status="failure")
        self.assertEqual(rc, 0)
        _, payload = self.sent_payload()
        self.assertIn("\u043f\u043e\u0432\u0440\u0435\u0436\u0434\u0435\u043d\u044b", payload["text"])
        self.assertIn("TEST-Broken.xml", payload["text"])

    # 9
    def test_no_results_build_error(self):
        rc, _ = self.run_notify(self.fixture("missing-dir"), job_status="failure")
        self.assertEqual(rc, 0)
        _, payload = self.sent_payload()
        self.assertIn("\U0001f6d1", payload["text"])
        self.assertNotIn("0 \u0442\u0435\u0441\u0442\u043e\u0432", payload["text"])

    # 10
    def test_zero_tests(self):
        rc, _ = self.run_notify(self.fixture("zero"))
        self.assertEqual(rc, 0)
        _, payload = self.sent_payload()
        self.assertIn("0 \u0442\u0435\u0441\u0442\u043e\u0432", payload["text"])
        self.assertNotIn("\U0001f6d1", payload["text"])

    # 11 (cancelled)
    def test_cancelled_not_sent(self):
        rc, out = self.run_notify(self.fixture("basic"), job_status="cancelled")
        self.assertEqual(rc, 0)
        self.assertEqual(self.server.requests, [])
        self.assertIn("cancelled", out)

    # 12 (missing secrets)
    def test_missing_secrets_skips(self):
        rc, out = self.run_notify(self.fixture("basic"), token="", chat="")
        self.assertEqual(rc, 0)
        self.assertEqual(self.server.requests, [])
        self.assertIn("skipped", out)

    # 13 (HTTP error)
    def test_http_error_soft(self):
        self.server.mode = "http_500"
        rc, out = self.run_notify(self.fixture("basic"))
        self.assertEqual(rc, 0)
        self.assertIn("HTTP 500", out)
        self.assertNotIn(FAKE_TOKEN, out)
        self.assertNotIn(FAKE_CHAT, out)

    # 14 (ok=false)
    def test_ok_false_soft(self):
        self.server.mode = "ok_false"
        rc, out = self.run_notify(self.fixture("basic"))
        self.assertEqual(rc, 0)
        self.assertIn("ok=false", out)
        self.assertNotIn(FAKE_TOKEN, out)

    # 15 (timeout)
    def test_timeout_soft(self):
        self.server.mode = "timeout"
        self.server.timeout_seconds = 2
        rc, out = self.run_notify(self.fixture("basic"), timeout=0.5)
        self.assertEqual(rc, 0)
        self.assertIn("timeout", out)
        self.assertNotIn(FAKE_TOKEN, out)

    # 16 (401 unauthorized + token leak check in error text)
    def test_unauthorized_sanitized(self):
        self.server.mode = "unauthorized"
        rc, out = self.run_notify(self.fixture("basic"))
        self.assertEqual(rc, 0)
        self.assertIn("HTTP 401", out)
        self.assertNotIn(FAKE_TOKEN, out)
        self.assertNotIn(FAKE_CHAT, out)

    # 17 (CI_NAME override for non-GHA platforms)
    def test_ci_name_override(self):
        rc, _ = self.run_notify(self.fixture("basic"), extra={"CI_NAME": "Jenkins"})
        self.assertEqual(rc, 0)
        _, payload = self.sent_payload()
        self.assertIn("(Jenkins)", payload["text"])

    # 18 (job failure preserved: notify exits 0 regardless => job status decided elsewhere)
    def test_exit_zero_on_all_error_modes(self):
        for mode in ("http_500", "ok_false", "unauthorized"):
            self.server.mode = mode
            rc, _ = self.run_notify(self.fixture("failure"), job_status="failure")
            self.assertEqual(rc, 0, f"notify must never fail the job (mode={mode})")


if __name__ == "__main__":
    unittest.main(verbosity=2)