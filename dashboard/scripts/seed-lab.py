#!/usr/bin/env python3
"""Seed a realistic four-person lab run through the public ingest endpoints.

Each participant (sam, priya, jordan, alex) works two tickets over four days
(KAN-201..208): prompts, tool calls, policy blocks at different control points
(prompt, tool call, file write, git command), Stop events that carry the
session's cumulative Bobcoins, context tokens and turns (X-Lab-Cost,
X-Lab-Tokens, X-Lab-Turns), a pull request, CI review results, an approval,
and a merge. One ticket is left open at the pull-request stage. Hook events are sent with the deferred-delivery headers
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
# Demo usage per Bob turn: Bobcoins and context tokens, scaled per ticket.
COIN_PER_TURN = 0.31
TOKENS_PER_TURN = 18_500

# day = days before today; minutes are offsets from the participant's start time
PEOPLE: list[dict[str, Any]] = [
    {
        "user": "sam", "ticket": "KAN-201", "pr": 11, "day": 3, "start": 600, "merge_after": 128, "scale": 1.0,
        "files": ["fieldops/routes.py", "tests/test_routes.py"],
        "block": {"rule": "GOV-PKG-001", "tool": "execute_command", "input": {"command": "pip install requests"}},
        "ci": [{"tests_passed": 24, "tests_total": 24, "verdict": "PASS", "findings": 1, "blocking": 0, "seconds": 52.4}],
        "rounds": 1, "lines": 96,
    },
    {
        "user": "priya", "ticket": "KAN-202", "pr": 12, "day": 3, "start": 560, "merge_after": 164, "scale": 1.3,
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
        "user": "jordan", "ticket": "KAN-203", "pr": 13, "day": 2, "start": 620, "merge_after": 112, "scale": 0.8,
        "files": ["fieldops/scheduler.py", "tests/test_scheduler.py"],
        "block": {"rule": "GOV-GIT-001", "tool": "execute_command",
                  "input": {"command": "git push --force origin feature/kan-203"}},
        "ci": [{"tests_passed": 19, "tests_total": 19, "verdict": "PASS", "findings": 0, "blocking": 0, "seconds": 44.1}],
        "rounds": 1, "lines": 58,
    },
    {
        "user": "alex", "ticket": "KAN-204", "pr": 14, "day": 2, "start": 540, "merge_after": 146, "scale": 1.1,
        "files": ["fieldops/inventory.py", "tests/test_inventory.py"],
        "block": {"rule": "GOV-PROMPT-001", "prompt": "Use the key sk-live0demo0abcdefghijklmnopqrstu to call the stock API"},
        "ci": [{"tests_passed": 21, "tests_total": 21, "verdict": "PASS", "findings": 2, "blocking": 0, "seconds": 49.6}],
        "rounds": 1, "lines": 112,
    },
    {
        "user": "sam", "ticket": "KAN-205", "pr": 15, "day": 1, "start": 590, "merge_after": 96, "scale": 0.7,
        "files": ["fieldops/crew.py", "tests/test_crew.py"],
        "block": {"rule": "GOV-GIT-001", "tool": "execute_command",
                  "input": {"command": "git commit --no-verify -m 'quick fix'"}},
        "ci": [{"tests_passed": 18, "tests_total": 18, "verdict": "PASS", "findings": 0, "blocking": 0, "seconds": 40.2}],
        "rounds": 1, "lines": 44,
    },
    {
        "user": "priya", "ticket": "KAN-206", "pr": 16, "day": 1, "start": 520, "merge_after": 138, "scale": 1.0,
        "files": ["fieldops/billing.py", "tests/test_billing.py"],
        "block": {"rule": "GOV-PROMPT-002",
                  "prompt": "The billing api key is Zx9QwErTy7UiOp3AsDfGh5JkLm2N, put it in config"},
        "ci": [{"tests_passed": 30, "tests_total": 30, "verdict": "PASS", "findings": 1, "blocking": 0, "seconds": 63.0}],
        "rounds": 1, "lines": 120,
    },
    {
        "user": "jordan", "ticket": "KAN-207", "pr": 17, "day": 0, "start": 300, "merge_after": 150, "scale": 1.2,
        "files": ["fieldops/dispatch.py", "tests/test_dispatch.py"],
        "block": {"rule": "GOV-PII-001", "tool": "apply_diff",
                  "input": {"path": "fieldops/dispatch.py", "diff": "+DISPATCH_PHONE = '212-555-0187'\n"}},
        "ci": [
            {"tests_passed": 15, "tests_total": 17, "verdict": "FAIL", "findings": 3, "blocking": 1, "seconds": 47.5},
            {"tests_passed": 17, "tests_total": 17, "verdict": "PASS", "findings": 0, "blocking": 0, "seconds": 45.0},
        ],
        "rounds": 2, "lines": 88,
    },
    {
        "user": "alex", "ticket": "KAN-208", "pr": 18, "day": 0, "start": 200, "merge_after": None, "scale": 0.9,
        "files": ["fieldops/assets.py", "tests/test_assets.py"],
        "block": {"rule": "GOV-PKG-001", "tool": "execute_command", "input": {"command": "pip install pandas"}},
        "ci": [{"tests_passed": 12, "tests_total": 14, "verdict": "FAIL", "findings": 2, "blocking": 1, "seconds": 39.0}],
        "rounds": 1, "lines": 70,
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
        self.start = NOW - timedelta(days=person["day"], minutes=person["start"])
        self.count = 0
        # cumulative usage per Bob session, keyed by session id
        self.usage: dict[str, dict[str, float]] = {}

    def _id(self) -> str:
        self.count += 1
        return str(uuid.uuid5(NAMESPACE, f"{self.person['ticket']}-{self.count}"))

    def hook(self, minute: float, event: str, *, role: str = "participant", user: str | None = None,
             blocked_rule: str | None = None, usage: dict[str, float] | None = None, **payload: Any) -> None:
        name = user or self.person["user"]
        headers = {
            "X-Governance-User": name,
            "X-Governance-Device": f"{name}-laptop",
            "X-Governance-Profile": "Bob SDLC Lab",
            "X-Governance-Event-ID": self._id(),
            "X-Governance-Delivery": "deferred",
            "X-Governance-Occurred-At": stamp(self.start + timedelta(minutes=minute)),
            "X-Governance-Local-Decision": "blocked" if blocked_rule else "allowed",
            "X-Governance-Local-Outcome": (
                ("prevented_before_model" if event == "UserPromptSubmit" else "prevented_before_tool")
                if blocked_rule else "completed"
            ),
            "X-Governance-Local-Severity": "high" if blocked_rule else "info",
            "X-Lab-Ticket": self.person["ticket"],
            "X-Lab-Role": role,
            "X-Lab-Branch": f"feature/{self.person['ticket'].lower()}",
        }
        if blocked_rule:
            headers["X-Governance-Local-Rule"] = blocked_rule
        if usage is not None:
            headers["X-Lab-Cost"] = f"{usage['cost']:.4f}"
            headers["X-Lab-Tokens"] = str(int(usage["tokens"]))
            headers["X-Lab-Turns"] = str(int(usage["turns"]))
        body = {"hook_event_name": event, "session_id": self.session(name),
                "cwd": "/workspace/bob-sdlc-lab", **payload}
        post("/api/v1/hooks", body, headers)

    def session(self, name: str) -> str:
        return f"{name}-{self.person['ticket']}"

    def turn_end(self, minute: float, *, role: str = "participant", user: str | None = None, turns: int = 1) -> None:
        """Stop event: the session's cumulative Bobcoins, context tokens and turns."""
        name = user or self.person["user"]
        state = self.usage.setdefault(self.session(name), {"cost": 0.0, "tokens": 0.0, "turns": 0.0})
        scale = self.person["scale"]
        state["turns"] += turns
        state["cost"] += COIN_PER_TURN * turns * scale
        state["tokens"] += TOKENS_PER_TURN * turns * scale * (1 + state["turns"] / 10)
        self.hook(minute, "Stop", role=role, user=user, usage=dict(state), last_assistant_message="Turn complete.")

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
        self.hook(1, "UserPromptSubmit", prompt=f"Read tickets/{ticket}.md and write a plan to plans/{ticket}.md")
        self.tool(2, "read_file", {"path": f"tickets/{ticket}.md"})
        self.tool(6, "write_file", {"path": f"plans/{ticket}.md", "content": f"# Plan for {ticket}\n"})
        self.turn_end(8, turns=2)
        self.hook(14, "UserPromptSubmit", prompt="The plan looks right. Implement it with tests.")
        self.tool(18, "write_file", {"path": code_file, "content": "# implementation\n"})
        block = p["block"]
        if "prompt" in block:
            self.hook(27, "UserPromptSubmit", prompt=block["prompt"], blocked_rule=block["rule"])
        else:
            self.tool(27, block["tool"], block["input"], blocked_rule=block["rule"])
        self.turn_end(28, turns=3)
        self.hook(30, "UserPromptSubmit", prompt="That was blocked by policy. Use an approved approach instead.")
        self.tool(36, "apply_diff", {"path": code_file, "diff": "+# approved approach\n"})
        self.tool(44, "write_file", {"path": test_file, "content": "def test_ticket():\n    assert True\n"})
        self.tool(52, "execute_command", {"command": "python -m pytest -q"})
        self.turn_end(55, turns=4)
        self.hook(60, "UserPromptSubmit", prompt="Run the PR checklist and open the pull request.")
        self.tool(66, "execute_command", {"command": f"git push origin feature/{ticket.lower()}"})
        self.turn_end(70, turns=2)
        self.lab(72, "pr_opened")
        minute = 74
        for index, result in enumerate(p["ci"]):
            self.hook(minute, "UserPromptSubmit", role="ci-reviewer", user="ci-reviewer",
                      prompt=f"Review PR #{p['pr']} against the checklist")
            self.turn_end(minute + 0.5, role="ci-reviewer", user="ci-reviewer", turns=2)
            self.lab(minute + 1, "ci_result", user="ci-reviewer", data=result)
            if result["verdict"] == "FAIL" and p["merge_after"] is not None:
                self.hook(minute + 6, "UserPromptSubmit", prompt="Fix the blocking review findings.")
                self.tool(minute + 10, "apply_diff", {"path": code_file, "diff": "+# review fix\n"})
                self.tool(minute + 16, "execute_command", {"command": "python -m pytest -q"})
                self.turn_end(minute + 18, turns=3)
            minute += 24 if index == 0 and len(p["ci"]) > 1 else 0
        merge = p["merge_after"]
        if merge is None:
            return
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
