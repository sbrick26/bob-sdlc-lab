from __future__ import annotations

import copy
import os
from typing import Any


POLICY_VERSION = os.environ.get("GOVERNANCE_POLICY_VERSION", "1.1.0")

DEFAULT_LAB_PACKAGE_ALLOWLIST = "flask,pytest,mcp,pyyaml"


def lab_python_allowlist() -> list[str]:
    """Approved Python packages, from LAB_PACKAGE_ALLOWLIST (comma separated)."""
    raw = os.environ.get("LAB_PACKAGE_ALLOWLIST", DEFAULT_LAB_PACKAGE_ALLOWLIST)
    names = [name.strip().lower().replace("_", "-") for name in raw.split(",")]
    return sorted({name for name in names if name})


PACKAGE_ALLOWLIST: dict[str, list[str]] = {
    "python": lab_python_allowlist(),
    "node": ["axios", "eslint", "express", "prettier", "react", "react-dom", "typescript"],
}

RULES: dict[str, dict[str, Any]] = {
    "GOV-PROMPT-001": {
        "name": "Known credential format",
        "description": "Blocks well-known API keys, access tokens, JWTs, and private-key formats before model processing.",
        "events": ["UserPromptSubmit"],
        "decision": "blocked",
        "severity": "high",
        "enforcement": "exit 2 before model",
        "remediation": "Remove the credential. Use an environment variable or the secret store.",
    },
    "GOV-PROMPT-002": {
        "name": "Labeled secret",
        "description": "Blocks a likely literal credential disclosed near api key, token, secret, password, or client secret language.",
        "events": ["UserPromptSubmit"],
        "decision": "blocked",
        "severity": "high",
        "enforcement": "exit 2 before model",
        "remediation": "Remove the credential. Use an environment variable or the secret store.",
    },
    "GOV-TOOL-001": {
        "name": "Credential in tool input",
        "description": "Blocks credential-shaped content before it is passed to a tool.",
        "events": ["PreToolUse"],
        "decision": "blocked",
        "severity": "high",
        "enforcement": "exit 2 before tool",
        "remediation": "Remove the credential. Use an environment variable or the secret store.",
    },
    "GOV-POST-001": {
        "name": "Credential in tool output",
        "description": "Records a finding and adds managed corrective context to Bob's next turn.",
        "events": ["PostToolUse"],
        "decision": "observed",
        "severity": "high",
        "enforcement": "next-turn context",
        "remediation": "Do not copy the credential from the tool output. Use an environment variable or the secret store.",
    },
    "GOV-RESP-001": {
        "name": "Credential in assistant response",
        "description": "Records credential-shaped content observed when the Bob response stops.",
        "events": ["Stop"],
        "decision": "observed",
        "severity": "high",
        "enforcement": "record only",
        "remediation": "Do not reuse the credential from the answer. Rotate it if it is real.",
    },
    "GOV-HOOK-001": {
        "name": "Unscannable payload",
        "description": "Blocks a hook payload that exceeds the configured inspection limit.",
        "events": ["UserPromptSubmit", "PreToolUse"],
        "decision": "blocked",
        "severity": "high",
        "enforcement": "exit 2 before model or tool",
        "remediation": "Send a smaller input.",
    },
    "GOV-PKG-001": {
        "name": "Unapproved package installation",
        "description": "Blocks package installation unless every requested dependency is on the approved Python or Node.js allowlist.",
        "events": ["PreToolUse"],
        "decision": "blocked",
        "severity": "high",
        "enforcement": "exit 2 before tool",
        "remediation": "Ask for the package to be added to the approved list, or use an approved one.",
        "configuration": {"allowlist": PACKAGE_ALLOWLIST},
    },
    "GOV-PII-001": {
        "name": "Unmasked customer phone number",
        "description": "Blocks a file write that contains an unmasked US phone number outside data/ and tests/.",
        "events": ["PreToolUse"],
        "decision": "blocked",
        "severity": "high",
        "enforcement": "exit 2 before tool",
        "remediation": "Mask phone numbers as 415-555-**** before writing.",
    },
    "GOV-GIT-001": {
        "name": "Unsafe git command",
        "description": "Blocks git commands that skip hooks, force-push, or push straight to main.",
        "events": ["PreToolUse"],
        "decision": "blocked",
        "severity": "high",
        "enforcement": "exit 2 before tool",
        "remediation": "Push your ticket branch without --no-verify or --force and open a PR.",
    },
}

SESSION_CONTEXT = (
    f"Managed Governance policy {POLICY_VERSION} is active. Never expose credentials "
    "in prompts, tool inputs, tool outputs, or responses. Use managed secret references."
)


def rule(rule_id: str) -> dict[str, Any]:
    return RULES[rule_id]


def prompt_rule_id(hits: list[str]) -> str:
    return "GOV-PROMPT-002" if hits and set(hits) == {"labeled secret"} else "GOV-PROMPT-001"


def default_policy_config() -> dict[str, Any]:
    rules = []
    for rule_id, definition in RULES.items():
        entry = {"rule_id": rule_id, "enabled": True}
        if "configuration" in definition:
            entry["configuration"] = copy.deepcopy(definition["configuration"])
        rules.append(entry)
    return {
        "name": "Bob Governance",
        "rules": rules,
        "offline": {
            "enforcement": "last_known_good",
            "queue_max_events": 500,
            "queue_max_bytes": 10_485_760,
            "retry_max_seconds": 300,
            "missing_policy_behavior": "fail_open",
        },
        "content": {
            "capture_prompts": True,
            "capture_tool_inputs": True,
            "capture_tool_outputs": True,
            "capture_responses": True,
            "redact_credentials": True,
        },
    }
