#!/usr/bin/env python3
"""Seed a large demo: 60 users in 6 teams, 400 tickets over the last 90 days.

Used to check that every chart and table stays readable at scale (top 10 plus
"Other", weekly buckets past 31 days, paginated tables). Each ticket sends a
short Bob session through the hook endpoint (prompts, tool calls, some blocks,
Stop events with cumulative Bobcoins, context tokens and turns) and lab events
(PR opened, CI result, merge). Event ids are deterministic, so a second run
inserts nothing new.

Usage:
  BASE_URL=http://localhost:8080 INGEST_TOKEN=lab-ingest-token python scripts/seed-scale.py
"""

from __future__ import annotations

import json
import os
import random
import sys
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080").rstrip("/")
TOKEN = os.environ.get("INGEST_TOKEN", "lab-ingest-token")
NAMESPACE = uuid.UUID("0f6c7a52-3b5e-4f3e-9d0f-6d2b3c1a9e44")
NOW = datetime.now(timezone.utc).replace(second=0, microsecond=0)
TEAMS = ["Platform", "Field Apps", "Payments", "Data", "Mobile", "Identity"]
USERS = [f"user{index:02d}" for index in range(1, 61)]
TICKETS = 400
DAYS = 90
BLOCKS = [
    ("GOV-PKG-001", "PreToolUse", "execute_command", {"command": "pip install requests"}),
    ("GOV-GIT-001", "PreToolUse", "execute_command", {"command": "git push --force origin main"}),
    ("GOV-PII-001", "PreToolUse", "write_file", {"path": "app/report.py", "content": "PHONE = '415-555-0142'"}),
    ("GOV-PROMPT-001", "UserPromptSubmit", None, None),
]


def stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def post(path: str, body: dict[str, Any], headers: dict[str, str] | None = None) -> None:
    request = urllib.request.Request(
        f"{BASE_URL}{path}", data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"POST {path} failed: HTTP {exc.code} {exc.read().decode(errors='replace')}")


def ticket_events(index: int) -> list[tuple[str, dict[str, Any], dict[str, str]]]:
    rng = random.Random(index)
    user = USERS[rng.randrange(len(USERS))]
    team = TEAMS[USERS.index(user) % len(TEAMS)]
    ticket = f"SCL-{1000 + index}"
    start = NOW - timedelta(days=rng.uniform(0, DAYS), minutes=rng.randrange(0, 600))
    session = f"{user}-{ticket}"
    events: list[tuple[str, dict[str, Any], dict[str, str]]] = []
    counter = [0]

    def eid() -> str:
        counter[0] += 1
        return str(uuid.uuid5(NAMESPACE, f"{ticket}-{counter[0]}"))

    def hook(minute: float, event: str, *, rule: str | None = None, usage: dict[str, float] | None = None,
             who: str = user, role: str = "participant", **payload: Any) -> None:
        headers = {
            "X-Governance-User": who, "X-Governance-Device": f"{who}-laptop", "X-Governance-Event-ID": eid(),
            "X-Governance-Delivery": "deferred", "X-Governance-Occurred-At": stamp(start + timedelta(minutes=minute)),
            "X-Governance-Local-Decision": "blocked" if rule else "allowed",
            "X-Governance-Local-Severity": "high" if rule else "info",
            "X-Lab-Ticket": ticket, "X-Lab-Role": role, "X-Lab-Branch": f"feature/{ticket.lower()}",
            "X-Hook-Prev-Ms": str(rng.randrange(80, 700)),
        }
        if role == "participant":
            headers["X-Governance-Team"] = team
        if rule:
            headers["X-Governance-Local-Rule"] = rule
        if usage:
            headers.update({"X-Lab-Cost": f"{usage['cost']:.4f}", "X-Lab-Tokens": str(int(usage["tokens"])), "X-Lab-Turns": str(int(usage["turns"]))})
        events.append(("/api/v1/hooks", {"hook_event_name": event, "session_id": session if role == "participant" else f"ci-{ticket}",
                                         "cwd": "/workspace/app", **payload}, headers))

    def lab(minute: float, kind: str, data: dict[str, Any] | None = None, who: str = user) -> None:
        events.append(("/api/v1/lab/events", {
            "kind": kind, "user": who, "ticket": ticket, "pr": None if kind == "ticket_started" else index,
            "data": data or {}, "occurred_at": stamp(start + timedelta(minutes=minute)), "event_id": eid(),
        }, {}))

    lab(0, "ticket_started")
    usage = {"cost": 0.0, "tokens": 0.0, "turns": 0.0}
    minute = 1.0
    for turn in range(rng.randrange(2, 7)):
        hook(minute, "UserPromptSubmit", prompt=f"Work on {ticket}, step {turn + 1}.")
        for call in range(rng.randrange(1, 4)):
            tool_use = f"{ticket}-{turn}-{call}"
            hook(minute + 1, "PreToolUse", tool_name="execute_command", tool_use_id=tool_use, tool_input={"command": "python -m pytest -q"})
            if rng.random() > 0.02:
                hook(minute + 1 + rng.uniform(0.05, 1.5), "PostToolUse", tool_name="execute_command", tool_use_id=tool_use, tool_response="passed")
        if rng.random() < 0.08:
            rule, event, tool, tool_input = BLOCKS[rng.randrange(len(BLOCKS))]
            if event == "UserPromptSubmit":
                hook(minute + 3, event, rule=rule, prompt="use key sk-live0demo0abcdefghijklmnopqrstu")
            else:
                hook(minute + 3, event, rule=rule, tool_name=tool, tool_use_id=f"{ticket}-b{turn}", tool_input=tool_input)
        usage["turns"] += rng.randrange(1, 5)
        usage["cost"] += rng.uniform(0.1, 0.9)
        usage["tokens"] += rng.uniform(5_000, 25_000)
        hook(minute + 5, "Stop", usage=dict(usage), last_assistant_message="Step done.")
        minute += rng.uniform(6, 25)
    lab(minute + 2, "pr_opened")
    verdict = "PASS" if rng.random() > 0.3 else "FAIL"
    hook(minute + 3, "UserPromptSubmit", who="ci-reviewer", role="ci-reviewer", prompt=f"Review PR #{index}")
    hook(minute + 4, "Stop", who="ci-reviewer", role="ci-reviewer", usage={"cost": rng.uniform(0.2, 0.6), "tokens": 8_000, "turns": 2})
    lab(minute + 5, "ci_result", {"verdict": verdict, "findings": rng.randrange(0, 4), "tests_passed": 20, "tests_total": 20}, who="ci-reviewer")
    if rng.random() < 0.85:
        lab(minute + rng.uniform(30, 60 * 30), "merged", {"approver": "maintainer", "review_rounds": 1 if verdict == "PASS" else 2}, who="maintainer")
    return events


def send_ticket(index: int) -> None:
    for path, body, headers in ticket_events(index):
        post(path, body, headers)


def main() -> int:
    with ThreadPoolExecutor(max_workers=8) as pool:
        for done, _ in enumerate(pool.map(send_ticket, range(TICKETS)), start=1):
            if done % 50 == 0:
                print(f"seeded {done} of {TICKETS} tickets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
