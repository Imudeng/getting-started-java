"""Telegram notification for CI runs.

Statistics come ONLY from JUnit XML (surefire format), never from Allure internals.
The script never changes the job status: every path exits 0 and API errors are
logged sanitized (token/chat id are stripped from any output).

Environment (non-secret): RESULT_DIR, PROJECT, WORKFLOW_NAME, RUN_BRANCH, RUN_SHA,
RUN_EVENT, RUN_URL, JOB_STATUS, TELEGRAM_TIMEOUT, TELEGRAM_API_BASE (mock hook),
CI_NAME (platform label in the message header, default "GitHub Actions").
Environment (secret, from CI secrets only): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
"""

import glob
import json
import os
import socket
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

DEFAULT_API_BASE = "https://api.telegram.org"
DEFAULT_TIMEOUT = 10.0

STATUS_OK = "\u2705 \u0412\u0441\u0435 \u0442\u0435\u0441\u0442\u044b \u0437\u0435\u043b\u0451\u043d\u044b\u0435"
STATUS_FAILED = "\u274c \u0422\u0435\u0441\u0442\u044b \u0443\u043f\u0430\u043b\u0438"
STATUS_JOB_ERROR_AFTER_TESTS = "\u274c \u0421\u0431\u043e\u0439 job'\u0430 \u043f\u043e\u0441\u043b\u0435 \u0442\u0435\u0441\u0442\u043e\u0432"
STATUS_NO_TESTS_RAN = "\U0001f6d1 \u0421\u0431\u043e\u0440\u043a\u0430/\u043f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043a\u0430 \u0443\u043f\u0430\u043b\u0438 \u2014 \u0442\u0435\u0441\u0442\u044b \u043d\u0435 \u0437\u0430\u043f\u0443\u0441\u043a\u0430\u043b\u0438\u0441\u044c"
STATUS_ZERO_TESTS = "\u26a0\ufe0f \u0422\u0435\u0441\u0442\u044b \u043d\u0435 \u043f\u0440\u043e\u0448\u043b\u0438: 0 \u0442\u0435\u0441\u0442\u043e\u0432"
STATUS_BROKEN_XML = "\u26a0\ufe0f \u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u044b \u043f\u043e\u0432\u0440\u0435\u0436\u0434\u0435\u043d\u044b (\u043d\u0435 \u0440\u0430\u0437\u043e\u0431\u0440\u0430\u043d JUnit XML)"


def sanitize(text: str, secrets) -> str:
    out = str(text)
    for value in secrets:
        if value and len(value) >= 4:
            out = out.replace(value, "***")
    return out


def parse_junit(result_dir):
    """Sum leaf <testsuite> nodes across TEST-*.xml. Never double-count nested suites."""
    files = sorted(glob.glob(os.path.join(result_dir, "TEST-*.xml")))
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    broken = []
    for path in files:
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            broken.append(os.path.basename(path))
            continue
        suites = _leaf_suites(root)
        if not suites:
            broken.append(os.path.basename(path))
            continue
        for suite in suites:
            for key in totals:
                totals[key] += int(suite.get(key, "0") or 0)
    totals["files"] = len(files)
    totals["broken"] = broken
    totals["passed"] = max(0, totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"])
    return totals


def _leaf_suites(node):
    if node.tag == "testsuite":
        children = [child for child in node if child.tag == "testsuite"]
        if children:
            found = []
            for child in children:
                found.extend(_leaf_suites(child))
            return found
        return [node]
    found = []
    for child in node:
        found.extend(_leaf_suites(child))
    return found


def decide_status(job_status, totals):
    if totals["broken"] and totals["files"] == len(totals["broken"]):
        return STATUS_BROKEN_XML
    if totals["files"] == 0:
        return STATUS_NO_TESTS_RAN
    if totals["tests"] == 0:
        return STATUS_ZERO_TESTS
    if totals["failures"] + totals["errors"] > 0:
        return STATUS_FAILED
    if job_status.lower() == "failure":
        return STATUS_JOB_ERROR_AFTER_TESTS
    return STATUS_OK


def build_message(env, totals, status):
    sha = (env.get("RUN_SHA", "") or "")[:7]
    lines = [
        f"{env.get('PROJECT', '?')} \u2014 {env.get('WORKFLOW_NAME', 'CI')} ({env.get('CI_NAME', 'GitHub Actions')})",
        f"{env.get('RUN_BRANCH', '?')} @ {sha} ({env.get('RUN_EVENT', 'push')})",
        f"\u0421\u0442\u0430\u0442\u0443\u0441: {status}",
    ]
    if status in (STATUS_BROKEN_XML,):
        lines.append("\u0424\u0430\u0439\u043b\u044b \u043d\u0435 \u0440\u0430\u0437\u043e\u0431\u0440\u0430\u043d\u044b: " + ", ".join(totals["broken"]))
    elif status == STATUS_NO_TESTS_RAN:
        lines.append("\u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430 \u043e\u0442\u0441\u0443\u0442\u0441\u0442\u0432\u0443\u0435\u0442: JUnit XML \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")
    elif totals["tests"] == 0 and status == STATUS_ZERO_TESTS:
        lines.append("passed 0 \u00b7 failed 0 \u00b7 errors 0 \u00b7 skipped 0 \u00b7 total 0")
    else:
        lines.append(
            "passed {passed} \u00b7 failed {failures} \u00b7 errors {errors} \u00b7 skipped {skipped} \u00b7 total {tests}".format(**totals)
        )
    run_url = env.get("RUN_URL", "")
    if run_url:
        lines.append(f"Run: {run_url}")
    return "\n".join(lines)


def send(token, chat_id, text, api_base, timeout):
    url = f"{api_base.rstrip('/')}/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            code = response.getcode()
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            return "timeout"
        return f"network error: {reason}"
    except TimeoutError:
        return "timeout"
    except OSError as exc:
        if isinstance(exc, socket.timeout) or "timed out" in str(exc).lower():
            return "timeout"  # Python < 3.10: bare socket.timeout escapes urlopen unwrapped
        return f"network error: {exc}"
    if code != 200:
        return f"HTTP {code}"
    try:
        ok = json.loads(body).get("ok")
    except (ValueError, AttributeError):
        return "malformed response"
    if ok is not True:
        return "ok=false"
    return None


def main():
    env = os.environ
    job_status = env.get("JOB_STATUS", "unknown")
    if job_status.lower() == "cancelled":
        print("notify skipped: job was cancelled")
        return 0
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("notify skipped: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set")
        return 0
    secrets = (token, chat_id)
    result_dir = env.get("RESULT_DIR", os.path.join("build", "test-results", "test"))
    try:
        totals = parse_junit(result_dir)
    except Exception as exc:  # defensive: parsing must never crash notification
        print(sanitize(f"notify: junit parse error: {exc}", secrets))
        totals = {"files": 0, "broken": [], "tests": 0, "failures": 0, "errors": 0, "skipped": 0, "passed": 0}
    status = decide_status(job_status, totals)
    message = build_message(env, totals, status)
    api_base = env.get("TELEGRAM_API_BASE", DEFAULT_API_BASE)
    try:
        timeout = float(env.get("TELEGRAM_TIMEOUT", DEFAULT_TIMEOUT))
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    error = send(token, chat_id, message, api_base, timeout)
    if error:
        print(sanitize(f"notify: telegram API error: {error}", secrets))
    else:
        print("notify: sent")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # belt and braces: notification must never fail a job
        for value in (os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")):
            if value and len(value) >= 4:
                exc = type(exc)(str(exc).replace(value, "***"))
        print(f"notify: unexpected error: {exc}")
        sys.exit(0)