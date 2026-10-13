#!/usr/bin/env python3
"""Load deterministic, non-sensitive showcase activity into a Governance instance."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


NAMESPACE = uuid.UUID("f1694d16-8bb4-4aa0-ad9c-582657508cb4")


def scenario(
    index: int,
    *,
    hours_ago: int,
    user: str,
    device: str,
    event: str,
    decision: str,
    rule: str | None = None,
    rule_name: str | None = None,
    tool: str | None = None,
    outcome: str = "completed",
    policy_ms: int | None = None,
    tool_ms: int | None = None,
    detail: str = "Policy evaluation completed",
) -> dict[str, Any]:
    occurred = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {
        "event_id": str(uuid.uuid5(NAMESPACE, f"governance-showcase-{index}")),
        "occurred_at": occurred.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "user_name": user,
        "device_name": device,
        "device_id": str(uuid.uuid5(NAMESPACE, device)),
        "organization": "Governance",
        "source": "showcase-seed",
        "delivery": "managed-hook",
        "profile_name": "Bob Governance",
        "profile_id": "showcase-managed-profile",
        "policy_version": "1.2.0",
        "bob_version": "2.1.0-insiders",
        "bob_channel": "insiders",
        "hook_event": event,
        "decision": decision,
        "rule_id": rule,
        "rule_name": rule_name,
        "severity": "high" if decision in {"blocked", "observed"} else "info",
        "workspace": ["payments-api", "customer-portal", "analytics-pipeline"][index % 3],
        "tool_name": tool,
        "tool_category": "tool" if tool else None,
        "tool_use_id": str(uuid.uuid5(NAMESPACE, f"tool-{index}"))[:20] if tool else None,
        "outcome": outcome,
        "duration_ms": policy_ms,
        "tool_duration_ms": tool_ms,
        "finding_count": 1 if decision in {"blocked", "observed"} else 0,
        "hook_status": "complete",
        "content_logged": 0,
        "detail": detail,
        "evidence": rule_name if rule else None,
        "session_id": str(uuid.uuid5(NAMESPACE, f"session-{index // 3}"))[:20],
    }


def records() -> list[dict[str, Any]]:
    rows = [
        scenario(0, hours_ago=1, user="maya.patel", device="Engineering Mac 014", event="PreToolUse", decision="blocked", rule="GOV-TOOL-001", rule_name="Credential in tool input", tool="shell", outcome="prevented_before_tool", policy_ms=7, detail="Credential-shaped value removed before tool execution"),
        scenario(1, hours_ago=2, user="alex.chen", device="Engineering Mac 008", event="PreToolUse", decision="blocked", rule="GOV-PKG-001", rule_name="Unapproved package installation", tool="shell", outcome="prevented_before_tool", policy_ms=9, detail="Package left-pad was not on the approved Node.js allowlist"),
        scenario(2, hours_ago=3, user="jordan.lee", device="Design Mac 003", event="UserPromptSubmit", decision="blocked", rule="GOV-PROMPT-002", rule_name="Labeled secret", outcome="prevented_before_model", policy_ms=5, detail="Labeled credential was removed before model processing"),
        scenario(3, hours_ago=5, user="maya.patel", device="Engineering Mac 014", event="PostToolUse", decision="observed", rule="GOV-POST-001", rule_name="Credential in tool output", tool="tavily-search", outcome="finding_added_to_next_turn", policy_ms=6, tool_ms=842, detail="Validator finding was added to Bob's next turn"),
        scenario(4, hours_ago=7, user="alex.chen", device="Engineering Mac 008", event="PreToolUse", decision="allowed", tool="shell", policy_ms=4, detail="Approved React package installation allowed"),
        scenario(5, hours_ago=10, user="jordan.lee", device="Design Mac 003", event="UserPromptSubmit", decision="allowed", policy_ms=3, detail="Managed environment reference allowed"),
        scenario(6, hours_ago=18, user="priya.shah", device="Data Mac 021", event="PreToolUse", decision="blocked", rule="GOV-PKG-001", rule_name="Unapproved package installation", tool="shell", outcome="prevented_before_tool", policy_ms=8, detail="Dependency manifest required governance review"),
        scenario(7, hours_ago=23, user="priya.shah", device="Data Mac 021", event="PostToolUse", decision="allowed", tool="python", policy_ms=5, tool_ms=1260, detail="Approved Python analysis completed"),
        scenario(8, hours_ago=27, user="maya.patel", device="Engineering Mac 014", event="UserPromptSubmit", decision="blocked", rule="GOV-PROMPT-001", rule_name="Known credential format", outcome="prevented_before_model", policy_ms=5, detail="Known credential format removed before model processing"),
        scenario(9, hours_ago=34, user="alex.chen", device="Engineering Mac 008", event="PostToolUse", decision="allowed", tool="github", policy_ms=4, tool_ms=635, detail="Repository lookup completed"),
        scenario(10, hours_ago=49, user="jordan.lee", device="Design Mac 003", event="Stop", decision="observed", rule="GOV-RESP-001", rule_name="Credential in assistant response", outcome="response_finding_recorded", policy_ms=6, detail="Response validator recorded a credential-shaped finding"),
        scenario(11, hours_ago=58, user="priya.shah", device="Data Mac 021", event="PreToolUse", decision="allowed", tool="tavily-search", policy_ms=3, detail="Research tool request allowed"),
        scenario(12, hours_ago=76, user="maya.patel", device="Engineering Mac 014", event="SessionStart", decision="allowed", outcome="managed_rules_added", policy_ms=2, detail="Managed governance context applied"),
        scenario(13, hours_ago=98, user="alex.chen", device="Engineering Mac 008", event="PreToolUse", decision="blocked", rule="GOV-TOOL-001", rule_name="Credential in tool input", tool="http", outcome="prevented_before_tool", policy_ms=6, detail="Credential-shaped HTTP argument removed before execution"),
        scenario(14, hours_ago=122, user="jordan.lee", device="Design Mac 003", event="PostToolUse", decision="allowed", tool="filesystem", policy_ms=4, tool_ms=92, detail="Workspace read completed"),
        scenario(15, hours_ago=146, user="priya.shah", device="Data Mac 021", event="PreToolUse", decision="blocked", rule="GOV-PKG-001", rule_name="Unapproved package installation", tool="shell", outcome="prevented_before_tool", policy_ms=7, detail="Unapproved Python dependency was blocked"),
        scenario(16, hours_ago=170, user="maya.patel", device="Engineering Mac 014", event="UserPromptSubmit", decision="allowed", policy_ms=3, detail="Prompt passed managed policy checks"),
        scenario(17, hours_ago=196, user="alex.chen", device="Engineering Mac 008", event="PostToolUse", decision="allowed", tool="tavily-search", policy_ms=5, tool_ms=711, detail="Research results passed post-tool validation"),
    ]
    return rows


def main() -> int:
    base_url = (os.environ.get("GOVERNANCE_URL") or "").rstrip("/")
    token = os.environ.get("INGEST_TOKEN") or ""
    if not base_url or not token:
        print("GOVERNANCE_URL and INGEST_TOKEN are required", file=sys.stderr)
        return 2
    body = json.dumps(records(), separators=(",", ":")).encode()
    request = urllib.request.Request(
        base_url + "/api/v1/events",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", "replace"), file=sys.stderr)
        return 1
    print(f"Accepted {result['accepted']} showcase events ({result['inserted']} new, {result['duplicates']} existing).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
