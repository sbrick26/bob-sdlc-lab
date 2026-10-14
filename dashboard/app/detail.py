"""Plain-language view of one event for the detail drawer.

Every field without a value is left out; nothing says "Not measured".
"""

from __future__ import annotations

import json
import os
import re
from datetime import timedelta
from typing import Any, Callable

from .metrics import control_point, is_ci, mask
from .lab import _parse

STATUS = {"blocked": "Blocked", "observed": "Flagged", "allowed": "Allowed", "error": "Error"}
EVENT_TITLES = {
    "UserPromptSubmit": "Prompt sent", "Stop": "Turn ended", "SessionStart": "Session started",
    "PostToolUse": "Tool finished", "lab.pr_opened": "PR opened", "lab.ci_result": "CI review result",
    "lab.approved": "PR approved", "lab.merged": "PR merged", "lab.ticket_started": "Ticket started",
    "lab.ticket_done": "Ticket done",
}
ATTEMPT_LINES = 6
ATTEMPT_CHARS = 480


def _tool_input(event: dict[str, Any]) -> Any:
    text = event.get("tool_input_content")
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def _command(event: dict[str, Any]) -> str:
    value = _tool_input(event)
    if isinstance(value, dict):
        return str(value.get("command") or value.get("cmd") or "")
    return value if isinstance(value, str) else ""


def _path(event: dict[str, Any]) -> str | None:
    value = _tool_input(event)
    if isinstance(value, dict):
        for key in ("path", "file_path", "target_file", "filePath", "file"):
            if value.get(key):
                return str(value[key])
    return event.get("lab_path")


def action(event: dict[str, Any]) -> tuple[str, str]:
    """(present, past) phrase for what the person did, from control point and tool."""
    point = control_point(event)
    if point == "Prompt submit":
        return "send a prompt", "sent a prompt"
    if point == "File write":
        path = _path(event)
        return (f"write to {path}", f"wrote to {path}") if path else ("write a file", "wrote a file")
    if point == "Git command":
        command = _command(event)
        if "--no-verify" in command:
            return "run a git command that skips the safety checks", "ran a git command that skips the safety checks"
        if re.search(r"(?:^|\s)(?:--force|-f)(?:\s|$)", command):
            return "run a git command that force-pushes", "ran a git command that force-pushes"
        if re.search(r"\bpush\s+origin\s+(?:\S+:)?main\b", command):
            return "push straight to main", "pushed straight to main"
        return "run a git command", "ran a git command"
    if point == "Tool call":
        if event.get("tool_name") in {None, "execute_command"}:
            return "run a command", "ran a command"
        tool = str(event["tool_name"]).replace("_", " ")
        return f"use {tool}", f"used {tool}"
    if point == "Tool output":
        return "receive tool output", "received tool output"
    if point == "Response":
        return "get an answer from Bob", "got an answer from Bob"
    if point == "Session start":
        return "start a Bob session", "started a Bob session"
    kind = str(event.get("hook_event") or "").removeprefix("lab.")
    pr = f"PR #{event['lab_pr']}" if event.get("lab_pr") is not None else "the PR"
    verdict = ((event.get("lab_data") or {}).get("verdict") or "").upper()
    lab_words = {
        "ci_result": (f"review {pr}", f"reviewed {pr}" + (f": {verdict}" if verdict else "")),
        "pr_opened": (f"open {pr}", f"opened {pr}"), "approved": (f"approve {pr}", f"approved {pr}"),
        "merged": (f"merge {pr}", f"merged {pr}"), "ticket_started": ("start the ticket", "started the ticket"),
        "ticket_done": ("finish the ticket", "finished the ticket"),
    }
    return lab_words.get(kind, (f"record {kind.replace('_', ' ')}", f"recorded {kind.replace('_', ' ')}"))


def local_time(value: Any, tz_offset: int = 0) -> str | None:
    parsed = _parse(value)
    if not parsed:
        return None
    local = parsed - timedelta(minutes=tz_offset)
    hour = local.hour % 12 or 12
    return f"{local.strftime('%b')} {local.day}, {hour}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"


def sentence(event: dict[str, Any], tz_offset: int = 0) -> str:
    """"Sam tried to run a git command on KAN-205 at Oct 12, 12:43 PM." Missing parts are left out."""
    person = "CI review" if event.get("lab_role") == "ci-reviewer" or event.get("user_name") == "ci-reviewer" else str(event.get("user_name") or "Someone")
    person = person[:1].upper() + person[1:]
    present, past = action(event)
    verb = f"tried to {present}" if event.get("decision") == "blocked" else past
    text = f"{person} {verb}"
    if event.get("lab_ticket"):
        text += f" on {event['lab_ticket']}"
    when = local_time(event.get("occurred_at"), tz_offset)
    if when:
        text += f" at {when}"
    return text + "."


def title(event: dict[str, Any]) -> str:
    if event.get("rule_name"):
        return str(event["rule_name"])
    hook = str(event.get("hook_event") or "")
    if hook == "PreToolUse":
        point = control_point(event)
        return {"File write": "File written", "Git command": "Git command run"}.get(
            point, "Command run" if event.get("tool_name") in {None, "execute_command"} else "Tool used"
        )
    return EVENT_TITLES.get(hook, hook or "Event")


def attempted(event: dict[str, Any], redact_fn: Callable[[Any], tuple[str, list[str]]] | None = None) -> str | None:
    """What was attempted: command, prompt, or file path plus snippet, masked, at most 6 lines."""
    point = control_point(event)
    text = ""
    if point == "Prompt submit":
        text = event.get("prompt_content") or ""
    elif point in {"Tool call", "File write", "Git command"}:
        value = _tool_input(event)
        if isinstance(value, dict):
            command = value.get("command") or value.get("cmd")
            body = value.get("content") or value.get("diff")
            if command:
                text = str(command)
            elif _path(event):
                text = f"{_path(event)}\n{body}" if body else str(_path(event))
            else:
                text = json.dumps(value, ensure_ascii=False, indent=1)
        elif value:
            text = str(value)
    elif point == "Tool output":
        text = event.get("tool_output_content") or ""
    elif point == "Response":
        text = event.get("response_content") or ""
    text = mask(str(text), redact_fn).strip()
    if not text:
        return None
    lines = text.splitlines()
    clipped = "\n".join(lines[:ATTEMPT_LINES])
    if len(clipped) > ATTEMPT_CHARS:
        clipped = clipped[:ATTEMPT_CHARS - 1].rstrip()
    return clipped + ("…" if clipped != text else "")


TOOL_WORDS = {
    "execute_command": "Run a command", "write_file": "Write a file", "apply_diff": "Edit a file",
    "insert_content": "Insert into a file", "search_and_replace": "Search and replace", "read_file": "Read a file",
    "list_files": "List files", "search_files": "Search files", "use_mcp_tool": "MCP tool", "access_mcp_resource": "MCP resource",
}
WRITE_TOOLS = {"write_file", "apply_diff", "insert_content", "search_and_replace"}


def _masked(text: Any, redact_fn: Callable[[Any], tuple[str, list[str]]] | None) -> str | None:
    if text in (None, ""):
        return None
    return mask(text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, indent=1), redact_fn)


def details(event: dict[str, Any], redact_fn: Callable[[Any], tuple[str, list[str]]] | None = None) -> dict[str, Any] | None:
    """What actually happened, by event type. Content is the stored, masked text, masked again."""
    hook = str(event.get("hook_event") or "")
    data = event.get("lab_data") or {}
    if hook == "UserPromptSubmit":
        text = _masked(event.get("prompt_content"), redact_fn)
        return {"kind": "prompt", "text": text, "chars": len(event.get("prompt_content") or "")} if text else None
    if hook in {"PreToolUse", "PostToolUse"}:
        tool = str(event.get("tool_name") or "")
        value = _tool_input(event)
        out: dict[str, Any] = {"kind": "tool", "tool": TOOL_WORDS.get(tool, tool.replace("_", " ") or "Tool"), "tool_name": tool}
        if isinstance(value, dict):
            if tool == "execute_command" or value.get("command"):
                out["command"] = _masked(value.get("command") or value.get("cmd"), redact_fn)
            elif tool in WRITE_TOOLS:
                out["path"] = _path(event)
                out["content"] = _masked(value.get("content") or value.get("diff") or value.get("replace") or "", redact_fn)
            elif tool in {"use_mcp_tool", "access_mcp_resource"}:
                out["fields"] = [{"label": str(key), "value": _masked(item, redact_fn) or ""} for key, item in value.items()][:12]
            else:
                out["fields"] = [{"label": str(key), "value": _masked(item, redact_fn) or ""} for key, item in value.items()][:12]
        elif value:
            out["content"] = _masked(value, redact_fn)
        if hook == "PostToolUse":
            out["output"] = _masked(event.get("tool_output_content"), redact_fn)
            run_ms = event.get("tool_run_ms")
            if isinstance(run_ms, (int, float)):
                out["run_time"] = f"{run_ms / 1000:.1f} s"
        return {key: item for key, item in out.items() if item not in (None, "", [])}
    if hook == "Stop":
        out = {"kind": "stop", "message": _masked(event.get("response_content"), redact_fn),
               "bobcoins": event.get("lab_cost"), "turns": event.get("lab_turns"), "tokens": event.get("lab_tokens")}
        return {key: item for key, item in out.items() if item not in (None, "")} if len(out) else None
    if hook == "SessionStart":
        out = {"kind": "session", "source": event.get("session_source"), "workspace": event.get("workspace")}
        return {key: item for key, item in out.items() if item not in (None, "", "no-folder")}
    if hook == "lab.ci_result":
        out = {
            "kind": "ci", "verdict": data.get("verdict"),
            "criteria": f"{data['criteria_met']} of {data['criteria_total']}" if data.get("criteria_total") is not None and data.get("criteria_met") is not None else None,
            "tests": f"{data['tests_passed']} of {data['tests_total']}" if data.get("tests_total") is not None and data.get("tests_passed") is not None else None,
            "findings": data.get("findings"), "findings_list": data.get("findings_list"), "blocking": data.get("blocking"),
            "duration": f"{data['seconds']:.0f} s" if isinstance(data.get("seconds"), (int, float)) else None,
            "pr_url": data.get("pr_url"), "run_url": data.get("run_url"), "pr": event.get("lab_pr"),
        }
        return {key: item for key, item in out.items() if item not in (None, "", [])}
    if hook in {"lab.pr_opened", "lab.approved", "lab.merged"}:
        out = {"kind": "pr", "title": data.get("title"), "pr": event.get("lab_pr"), "pr_url": data.get("pr_url"),
               "approver": data.get("approver"), "lines_changed": data.get("lines_changed"), "review_rounds": data.get("review_rounds")}
        return {key: item for key, item in out.items() if item not in (None, "")}
    return None


def _fields(items: list[tuple[str, Any, str | None]]) -> list[dict[str, Any]]:
    out = []
    for label, value, href in items:
        if value in (None, "", "unknown", "no-folder"):
            continue
        entry: dict[str, Any] = {"label": label, "value": value}
        if href:
            entry["href"] = href
        out.append(entry)
    return out


def jira_link(ticket: str | None) -> str | None:
    base = (os.environ.get("JIRA_BASE_URL") or "").strip().rstrip("/")
    return f"{base}/browse/{ticket}" if base and ticket else None


def build(
    event: dict[str, Any], rule: dict[str, Any] | None, tz_offset: int = 0,
    redact_fn: Callable[[Any], tuple[str, list[str]]] | None = None,
) -> dict[str, Any]:
    check_ms = event.get("check_ms")
    tool_ms = event.get("tool_run_ms") if event.get("decision") != "blocked" else None
    session = event.get("session_id")
    view: dict[str, Any] = {
        "title": title(event),
        "status": STATUS.get(str(event.get("decision")), str(event.get("decision") or "")),
        "decision": event.get("decision"),
        "sentence": sentence(event, tz_offset),
        "attempted": attempted(event, redact_fn) if event.get("rule_id") else None,
        "details": details(event, redact_fn),
        "context": _fields([
            ("User", "Automated review (CI)" if is_ci(event) else event.get("user_name"), None),
            ("Team", event.get("team"), None),
            ("Ticket", event.get("lab_ticket"), jira_link(event.get("lab_ticket"))),
            ("Branch", event.get("lab_branch"), None),
            ("Repository", event.get("workspace"), None),
            ("Session", str(session)[:8] if session and session != "unknown" else None,
             f"#/audit?session={session}" if session and session != "unknown" else None),
            ("Time", local_time(event.get("occurred_at"), tz_offset), None),
        ]),
        "technical": _fields([
            ("Event", str(event.get("hook_event") or "").removeprefix("lab.") or None, None),
            ("Session source", event.get("session_source"), None),
            ("Control point", control_point(event) if not str(event.get("hook_event") or "").startswith("lab.") else None, None),
            ("Tool", event.get("tool_name"), None),
            ("Governance check time", f"{check_ms:g} ms" if isinstance(check_ms, (int, float)) else None, None),
            ("Tool run time", f"{tool_ms / 1000:.1f} s" if isinstance(tool_ms, (int, float)) else None, None),
            ("Previous call round trip", f"{event['hook_rtt_prev_ms']} ms" if isinstance(event.get("hook_rtt_prev_ms"), int) else None, None),
            ("Device", event.get("device_name"), None),
            ("Severity", event.get("severity"), None),
            ("Event id", event.get("event_id"), None),
        ]),
    }
    if event.get("rule_id") and rule:
        view["rule_id"] = event["rule_id"]
        view["why"] = rule.get("description")
        view["remediation"] = rule.get("remediation")
    return {key: value for key, value in view.items() if value not in (None, "", [])}
