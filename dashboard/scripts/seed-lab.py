#!/usr/bin/env python3
"""Seed a realistic four-person lab run through the public ingest endpoints.

Each participant (sam, priya, jordan, alex) works one ticket (KAN-201..204):
prompts, tool calls, one policy block, a pull request, CI review results, an
approval, and a merge. Hook events are sent with the deferred-delivery headers
so they carry past timestamps; that is the same path a hook client uses to
replay events it recorded while offline. Event ids are deterministic, so a
second run inserts nothing new.

Usage:
  BASE_URL=http://localhost:8080 INGEST_TOKEN=lab-ingest-token python scripts/seed-lab.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080").rstrip("/")
TOKEN = os.environ.get("INGEST_TOKEN", "lab-ingest-token")
NAMESPACE = uuid.UUID("5b1f3c2e-8d74-4c0b-9a51-6f0f2d8e7a10")
NOW = datetime.now(timezone.utc).replace(second=0, microsecond=0)
COST_PER_PROMPT = 0.35  # demo usage credits per prompt, sent as X-Lab-Cost

# minutes are offsets from the participant's start time
PEOPLE: list[dict[str, Any]] = [
    {
        "user": "sam", "ticket": "KAN-201", "pr": 11, "start": 210, "merge_after": 128,
        "files": ["fieldops/routes.py", "tests/test_routes.py"],
        "block": {"rule": "GOV-PKG-001", "tool": "execute_command", "input": {"command": "pip install requests"}},
        "ci": [{"tests_passed": 24, "tests_total": 24, "verdict": "PASS", "findings": 1, "blocking": 0, "seconds": 52.4}],
        "rounds": 1, "lines": 96,
    },
    {
        "user": "priya", "ticket": "KAN-202", "pr": 12, "start": 205, "merge_after": 164,
        "files": ["fieldops/report.py", "tests/test_report.py"],
        "block": {"rule": "GOV-PII-001", "tool": "write_file",
                  "input": {"path": "fieldops/report.py", "content": "SUPPORT_LINE = '415-555-0142'\n"}},
        "ci": [
            {"tests_passed": 22, "tests_total": 25, "verdict": "FAIL", "findings": 4, "blocking": 2, "seconds": 61.0},
            {"tests_passed": 25, "tests_total": 25, "verdict": "PASS", "findings": 1, "blocking": 0, "seconds": 57.8},
        ],
        "rounds": 2, "lines": 141,
    },
    {
        "user": "jordan", "ticket": "KAN-203", "pr": 13, "start": 200, "merge_after": 112,
        "files": ["fieldops/scheduler.py", "tests/test_scheduler.py"],
        "block": {"rule": "GOV-GIT-001", "tool": "execute_command",
                  "input": {"command": "git push --force origin feature/kan-203"}},
        "ci": [{"tests_passed": 19, "tests_total": 19, "verdict": "PASS", "findings": 0, "blocking": 0, "seconds": 44.1}],
        "rounds": 1, "lines": 58,
    },
    {
        "user": "alex", "ticket": "KAN-204", "pr": 14, "start": 195, "merge_after": 146,
        "files": ["fieldops/inventory.py", "tests/test_inventory.py"],
        "block": {"rule": "GOV-PKG-001", "tool": "execute_command", "input": {"command": "pip install pandas"}},
        "ci": [{"tests_passed": 21, "tests_total": 21, "verdict": "PASS", "findings": 2, "blocking": 0, "seconds": 49.6}],
        "rounds": 1, "lines": 112,
    },
]


def stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def post(path: str, body: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{BASE_URL}{path}", data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"POST {path} failed: HTTP {exc.code} {exc.read().decode(errors='replace')}")


class Run:
    def __init__(self, person: dict[str, Any]):
        self.person = person
        self.start = NOW - timedelta(minutes=person["start"])
        self.count = 0

    def _id(self) -> str:
        self.count += 1
        return str(uuid.uuid5(NAMESPACE, f"{self.person['ticket']}-{self.count}"))

    def hook(self, minute: float, event: str, *, role: str = "participant", user: str | None = None,
             blocked_rule: str | None = None, cost: float | None = None, **payload: Any) -> None:
        name = user or self.person["user"]
        headers = {
            "X-Governance-User": name,
            "X-Governance-Device": f"{name}-laptop",
            "X-Governance-Profile": "Bob SDLC Lab",
            "X-Governance-Event-ID": self._id(),
            "X-Governance-Delivery": "deferred",
            "X-Governance-Occurred-At": stamp(self.start + timedelta(minutes=minute)),
            "X-Governance-Local-Decision": "blocked" if blocked_rule else "allowed",
            "X-Governance-Local-Outcome": "prevented_before_tool" if blocked_rule else "completed",
            "X-Governance-Local-Severity": "high" if blocked_rule else "info",
            "X-Lab-Ticket": self.person["ticket"],
            "X-Lab-Role": role,
            "X-Lab-Branch": f"feature/{self.person['ticket'].lower()}",
        }
        if blocked_rule:
            headers["X-Governance-Local-Rule"] = blocked_rule
        if cost is not None:
            headers["X-Lab-Cost"] = str(cost)
        body = {"hook_event_name": event, "session_id": f"{name}-{self.person['ticket']}",
                "cwd": "/workspace/bob-sdlc-lab", **payload}
        post("/api/v1/hooks", body, headers)

    def lab(self, minute: float, kind: str, *, user: str | None = None, data: dict[str, Any] | None = None) -> None:
        post("/api/v1/lab/events", {
            "kind": kind, "user": user or self.person["user"], "ticket": self.person["ticket"],
            "pr": None if kind in {"ticket_started"} else self.person["pr"], "data": data or {},
            "branch": f"feature/{self.person['ticket'].lower()}",
            "occurred_at": stamp(self.start + timedelta(minutes=minute)), "event_id": self._id(),
        })

    def tool(self, minute: float, tool: str, tool_input: dict[str, Any], **extra: Any) -> None:
        tool_use = f"{self.person['ticket']}-tool-{self.count}"
        self.hook(minute, "PreToolUse", tool_name=tool, tool_use_id=tool_use, tool_input=tool_input, **extra)
        if not extra.get("blocked_rule"):
            self.hook(minute + 0.5, "PostToolUse", tool_name=tool, tool_use_id=tool_use,
                      tool_input=tool_input, tool_response="ok")

    def play(self) -> None:
        p = self.person
        ticket, code_file, test_file = p["ticket"], p["files"][0], p["files"][1]
        self.lab(0, "ticket_started")
        self.hook(0.5, "SessionStart")
        self.hook(1, "UserPromptSubmit", prompt=f"Read tickets/{ticket}.md and write a plan to plans/{ticket}.md", cost=COST_PER_PROMPT)
        self.tool(2, "read_file", {"path": f"tickets/{ticket}.md"})
        self.tool(6, "write_file", {"path": f"plans/{ticket}.md", "content": f"# Plan for {ticket}\n"})
        self.hook(14, "UserPromptSubmit", prompt="The plan looks right. Implement it with tests.", cost=COST_PER_PROMPT)
        self.tool(18, "write_file", {"path": code_file, "content": "# implementation\n"})
        block = p["block"]
        self.tool(27, block["tool"], block["input"], blocked_rule=block["rule"])
        self.hook(30, "UserPromptSubmit", prompt="That was blocked by policy. Use an approved approach instead.", cost=COST_PER_PROMPT)
        self.tool(36, "apply_diff", {"path": code_file, "diff": "+# approved approach\n"})
        self.tool(44, "write_file", {"path": test_file, "content": "def test_ticket():\n    assert True\n"})
        self.tool(52, "execute_command", {"command": "python -m pytest -q"})
        self.hook(60, "UserPromptSubmit", prompt="Run the PR checklist and open the pull request.", cost=COST_PER_PROMPT)
        self.tool(66, "execute_command", {"command": f"git push origin feature/{ticket.lower()}"})
        self.hook(70, "Stop", last_assistant_message="Pull request opened.")
        self.lab(72, "pr_opened")
        minute = 74
        for index, result in enumerate(p["ci"]):
            self.hook(minute, "UserPromptSubmit", role="ci-reviewer", user="ci-reviewer",
                      prompt=f"Review PR #{p['pr']} against the checklist", cost=COST_PER_PROMPT)
            self.lab(minute + 1, "ci_result", user="ci-reviewer", data=result)
            if result["verdict"] == "FAIL":
                self.hook(minute + 6, "UserPromptSubmit", prompt="Fix the blocking review findings.", cost=COST_PER_PROMPT)
                self.tool(minute + 10, "apply_diff", {"path": code_file, "diff": "+# review fix\n"})
                self.tool(minute + 16, "execute_command", {"command": "python -m pytest -q"})
            minute += 24 if index == 0 and len(p["ci"]) > 1 else 0
        merge = p["merge_after"]
        self.lab(merge - 6, "approved", user="guide")
        self.lab(merge, "merged", user="guide",
                 data={"approver": "guide", "review_rounds": p["rounds"], "lines_changed": p["lines"]})
        self.lab(merge + 1, "ticket_done")


def main() -> int:
    for person in PEOPLE:
        Run(person).play()
        print(f"seeded {person['ticket']} for {person['user']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
