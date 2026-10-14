"""Page summaries for the dashboard: Overview, Violations, Usage and ROI, Rules.

Every function takes the stored event rows and derives its numbers from them.
Nothing here writes to storage.

Usage numbers (Bobcoins, context tokens, turns) come from the X-Lab-Cost,
X-Lab-Tokens and X-Lab-Turns headers. On a Stop event those values are
cumulative for the Bob session, so a session's usage is the MAX value seen for
that session_id. To place spend in time, each Stop event contributes only the
increase over the highest value seen earlier in the same session (its delta);
the deltas of one session add up to its maximum. A cost on any other event
(older hook clients sent one per prompt) is not cumulative and counts as is.
"""

from __future__ import annotations

import json
import os
import re
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable, Iterable

from . import lab


FILE_WRITE_TOOLS = {"write_file", "apply_diff", "insert_content", "search_and_replace"}
CONTROL_POINTS = ("Prompt submit", "Tool call", "File write", "Git command", "Tool output", "Response")
RULE_CONTROL_POINTS = {
    "GOV-PROMPT-001": "Prompt submit",
    "GOV-PROMPT-002": "Prompt submit",
    "GOV-TOOL-001": "Tool call",
    "GOV-POST-001": "Tool output",
    "GOV-RESP-001": "Response",
    "GOV-HOOK-001": "Prompt submit or tool call",
    "GOV-PKG-001": "Tool call",
    "GOV-PII-001": "File write",
    "GOV-GIT-001": "Git command",
}
RULE_CHECKS = {
    "GOV-PROMPT-001": "A known key or token format in a prompt, such as sk-, ghp_, AKIA, a JWT or a private key.",
    "GOV-PROMPT-002": "A long secret-looking value written next to words like api key, token, secret or password.",
    "GOV-TOOL-001": "A credential inside the input Bob is about to pass to a tool.",
    "GOV-POST-001": "A credential inside a tool's output. Bob gets a warning on its next turn.",
    "GOV-RESP-001": "A credential inside Bob's final answer. Recorded only.",
    "GOV-HOOK-001": "A hook payload too large to inspect.",
    "GOV-PKG-001": "A pip or npm install of a package that is not on the approved list.",
    "GOV-PII-001": "An unmasked US phone number written to a file outside data/ and tests/.",
    "GOV-GIT-001": "A git command that skips hooks, force-pushes or pushes straight to main.",
}
EXCERPT_MAX = 80
PHONE = re.compile(r"\b(\d{3}-\d{3}-)\d{4}\b")
LONG_TOKEN = re.compile(r"(?<![A-Za-z0-9])(?=[A-Za-z0-9_+/=-]*\d)(?=[A-Za-z0-9_+/=-]*[A-Za-z])[A-Za-z0-9_+/=-]{24,}")
LABELED = re.compile(r"(?i)\b(api[_ -]?key|token|secret|password|passwd|pwd)(\s*[:=]\s*)([\"']?)(?!\[REDACTED)([^\s\"',;]{4,})")


DEFAULT_USD_RATE = 0.50
USD_RATE_BASIS = "IBM enterprise pack price ($500 per 1,000 Bobcoins)"


def usd_rate() -> float | None:
    """USD per Bobcoin.

    Defaults to 0.50 (IBM enterprise packs are $500 per 1,000 Bobcoins).
    BOBCOIN_USD_RATE overrides it; "off", "none" or 0 turns USD off (None).
    """
    raw = os.environ.get("BOBCOIN_USD_RATE")
    if raw is None or not raw.strip():
        return DEFAULT_USD_RATE
    try:
        rate = float(raw.strip())
    except ValueError:
        return None
    return rate if rate > 0 else None


def usd_rate_basis(rate: float | None) -> str | None:
    if rate is None:
        return None
    if rate == DEFAULT_USD_RATE and not (os.environ.get("BOBCOIN_USD_RATE") or "").strip():
        return USD_RATE_BASIS
    return "BOBCOIN_USD_RATE setting"


def to_usd(bobcoins: float | None, rate: float | None) -> float | None:
    """Bobcoins times the rate, rounded half up to cents (3.87 BC at 0.50 is 1.94)."""
    if bobcoins is None or rate is None:
        return None
    value = Decimal(str(bobcoins)) * Decimal(str(rate))
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _parse(value: Any) -> datetime | None:
    return lab._parse(value)


def _is_hook(row: dict[str, Any]) -> bool:
    return row.get("source") != "lab"


def _lab_kind(row: dict[str, Any]) -> str | None:
    return row.get("lab_kind") if row.get("source") == "lab" else None


def _session_key(row: dict[str, Any]) -> str:
    session = row.get("session_id")
    return str(session) if session and session != "unknown" else f"event:{row.get('event_id')}"


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


# ---------------------------------------------------------------- usage deltas

def usage_deltas(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """One record per event that adds usage: Bobcoins, context tokens, turns.

    Cumulative values (cost on Stop events, tokens and turns on any event) add
    only their increase over the session's running maximum.
    """
    ordered = sorted(
        (row for row in rows if any(row.get(key) is not None for key in ("lab_cost", "lab_tokens", "lab_turns"))),
        key=lambda row: str(row.get("occurred_at") or ""),
    )
    running: dict[tuple[str, str], float] = {}
    deltas = []
    for row in ordered:
        session = _session_key(row)
        record = {
            "occurred_at": row.get("occurred_at"), "user": row.get("user_name"), "ci": is_ci(row),
            "ticket": row.get("lab_ticket"), "session": session, "team": row.get("team"),
            "bobcoins": None, "tokens": None, "turns": None,
        }
        for field, key in (("lab_cost", "bobcoins"), ("lab_tokens", "tokens"), ("lab_turns", "turns")):
            value = row.get(field)
            if value is None:
                continue
            value = float(value)
            cumulative = field != "lab_cost" or row.get("hook_event") == "Stop"
            if cumulative:
                previous = running.get((session, key), 0.0)
                running[(session, key)] = max(previous, value)
                record[key] = max(0.0, value - previous)
            else:
                record[key] = value
        deltas.append(record)
    return deltas


def _sum(records: Iterable[dict[str, Any]], key: str) -> float | None:
    values = [record[key] for record in records if record.get(key) is not None]
    return sum(values) if values else None


def bobcoins_by_ticket(rows: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for record in usage_deltas(rows):
        if record["ticket"] and record["bobcoins"] is not None:
            totals[str(record["ticket"])] += record["bobcoins"]
    return {ticket: round(value, 4) for ticket, value in totals.items()}


# ---------------------------------------------------------------- time buckets

def _local(value: datetime, tz_offset: int) -> datetime:
    """Shift UTC to the viewer's local clock. tz_offset is JavaScript's getTimezoneOffset()."""
    return value - timedelta(minutes=tz_offset)


def _buckets(times: list[datetime], tz_offset: int = 0) -> tuple[str, list[str]]:
    """Hour buckets when all data sits in one local day, day buckets otherwise."""
    if not times:
        return "day", []
    local = [_local(value, tz_offset) for value in times]
    first, last = min(local), max(local)
    if first.date() == last.date():
        cursor = first.replace(minute=0, second=0, microsecond=0)
        end = last.replace(minute=0, second=0, microsecond=0)
        labels = []
        while cursor <= end:
            labels.append(cursor.strftime("%Y-%m-%dT%H:00:00"))
            cursor += timedelta(hours=1)
        return "hour", labels
    cursor, labels = first.date(), []
    while cursor <= last.date():
        labels.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return "day", labels


def _bucket_of(value: Any, granularity: str, tz_offset: int = 0) -> str | None:
    parsed = _parse(value)
    if not parsed:
        return None
    parsed = _local(parsed, tz_offset)
    return parsed.strftime("%Y-%m-%dT%H:00:00") if granularity == "hour" else parsed.date().isoformat()


def _times(rows: Iterable[dict[str, Any]]) -> list[datetime]:
    return [parsed for parsed in (_parse(row.get("occurred_at")) for row in rows) if parsed]


# ---------------------------------------------------------------- control point and excerpt

def _tool_input(row: dict[str, Any]) -> Any:
    text = row.get("tool_input_content")
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def control_point(row: dict[str, Any]) -> str:
    """Where in Bob's loop the control ran, from hook_event_name and tool_name."""
    event = row.get("hook_event")
    tool = row.get("tool_name")
    if event == "UserPromptSubmit":
        return "Prompt submit"
    if event == "PreToolUse":
        if row.get("rule_id") == "GOV-GIT-001":
            return "Git command"
        if row.get("rule_id") == "GOV-PII-001" or tool in FILE_WRITE_TOOLS:
            return "File write"
        if tool == "execute_command":
            value = _tool_input(row)
            command = value.get("command") if isinstance(value, dict) else value
            if isinstance(command, str) and re.match(r"\s*git\b", command):
                return "Git command"
        return "Tool call"
    if event == "PostToolUse":
        return "Tool output"
    if event == "Stop":
        return "Response"
    if event == "SessionStart":
        return "Session start"
    if str(event or "").startswith("lab."):
        return "Lab event"
    return str(event or "Unknown")


def mask(text: str, redact_fn: Callable[[Any], tuple[str, list[str]]] | None = None) -> str:
    """Redact credentials with the ingest redaction, then mask anything else that looks like one."""
    if redact_fn is not None:
        text = redact_fn(text)[0]
    text = LABELED.sub(lambda match: f"{match.group(1)}{match.group(2)}{match.group(3)}****", text)
    text = LONG_TOKEN.sub(lambda match: match.group(0)[:4] + "****", text)
    return PHONE.sub(lambda match: f"{match.group(1)}****", text)


def excerpt(row: dict[str, Any], redact_fn: Callable[[Any], tuple[str, list[str]]] | None = None) -> str:
    """At most 80 characters of what was attempted, redacted and masked."""
    point = control_point(row)
    text = ""
    if point == "Prompt submit":
        text = row.get("prompt_content") or ""
    elif point in {"Tool call", "File write", "Git command"}:
        value = _tool_input(row)
        if isinstance(value, dict):
            command = value.get("command") or value.get("cmd")
            path = next((value.get(key) for key in ("path", "file_path", "target_file") if value.get(key)), None)
            body = value.get("content") or value.get("diff")
            if command:
                text = str(command)
            elif path:
                text = f"{path}: {body}" if body else str(path)
            else:
                text = json.dumps(value, ensure_ascii=False)
        elif value:
            text = str(value)
    elif point == "Tool output":
        text = row.get("tool_output_content") or ""
    elif point == "Response":
        text = row.get("response_content") or ""
    if not text:
        text = row.get("detail") or ""
    text = re.sub(r"\s+", " ", mask(str(text), redact_fn)).strip()
    return text if len(text) <= EXCERPT_MAX else text[:EXCERPT_MAX - 1].rstrip() + "…"


# ---------------------------------------------------------------- shared pieces

CI_LABEL = "Automated review (CI)"
CI_ROLE = "ci-reviewer"


def is_ci(row: dict[str, Any]) -> bool:
    """The CI reviewer is automation, not a person."""
    return row.get("lab_role") == CI_ROLE or row.get("user_name") == CI_ROLE or row.get("user") == CI_ROLE


def _users(rows: list[dict[str, Any]], board: list[dict[str, Any]]) -> list[str]:
    """People only: the CI reviewer is left out."""
    names = {str(row["user_name"]) for row in rows if _is_hook(row) and row.get("user_name") and not is_ci(row)}
    names.update(str(entry["user"]) for entry in board if entry.get("user") and entry["user"] != CI_ROLE)
    return sorted(names)


def _ticket_rows(rows: list[dict[str, Any]], board: list[dict[str, Any]], rate: float | None) -> list[dict[str, Any]]:
    by_ticket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("lab_ticket"):
            by_ticket[str(row["lab_ticket"])].append(row)
    deltas = usage_deltas(rows)
    result = []
    for entry in board:
        items = sorted(by_ticket[entry["ticket"]], key=lambda item: str(item.get("occurred_at") or ""))
        pr_opened = next((item for item in items if _lab_kind(item) == "pr_opened"), None)
        pr_opened_at = pr_opened.get("occurred_at") if pr_opened else None
        ticket_deltas = [record for record in deltas if record["ticket"] == entry["ticket"]]
        bobcoins = _round(_sum(ticket_deltas, "bobcoins"))
        tokens = _sum(ticket_deltas, "tokens")
        result.append({
            "ticket": entry["ticket"], "user": entry["user"], "status": entry["status"],
            "started_at": entry["started_at"], "pr_opened_at": pr_opened_at, "merged_at": entry["merged_at"],
            "minutes_to_pr": lab._minutes(entry["started_at"], pr_opened_at) if pr_opened_at else None,
            "minutes_to_merge": lab._minutes(entry["started_at"], entry["merged_at"]) if entry["merged_at"] else None,
            "bobcoins": bobcoins, "usd": to_usd(bobcoins, rate),
            "tokens": None if tokens is None else int(tokens),
            "verdict": entry["ci"]["verdict"], "findings": entry["ci"]["findings"],
            "first_try_pass": entry["ci"]["first_try_pass"], "ci_runs": entry["ci"]["runs"],
            "pr": entry["pr"], "blocks": entry["blocks"],
        })
    return result


# ---------------------------------------------------------------- Violations

def violation_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("rule_id") and row.get("decision") in {"blocked", "observed"}]


# ---------------------------------------------------------------- Rules

def rules_summary(rows: list[dict[str, Any]], catalog: dict[str, dict[str, Any]], enabled: dict[str, bool]) -> dict[str, Any]:
    found = violation_rows(rows)
    result = []
    for rule_id, definition in catalog.items():
        mine = [row for row in found if row.get("rule_id") == rule_id]
        result.append({
            "rule_id": rule_id, "name": definition.get("name"),
            "checks": RULE_CHECKS.get(rule_id, definition.get("description")),
            "control_point": RULE_CONTROL_POINTS.get(rule_id, ", ".join(definition.get("events", []))),
            "action": definition.get("decision"), "enabled": enabled.get(rule_id, True),
            "blocked": sum(row.get("decision") == "blocked" for row in mine),
            "observed": sum(row.get("decision") == "observed" for row in mine),
            "last_fired": max((str(row.get("occurred_at")) for row in mine), default=None),
        })
    return {"count": len(result), "rules": result}


# ---------------------------------------------------------------- CSV

CSV_COLUMNS = (
    ("time", "occurred_at"), ("user", "user_name"), ("team", "team"), ("ticket", "lab_ticket"), ("role", "lab_role"),
    ("event_type", "hook_event"), ("control_point", None), ("tool", "tool_name"), ("decision", "decision"),
    ("rule_id", "rule_id"), ("rule_name", "rule_name"), ("severity", "severity"), ("outcome", "outcome"),
    ("detail", None), ("session", "session_id"), ("bobcoins", "lab_cost"), ("usd", None),
    ("context_tokens", "lab_tokens"), ("turns", "lab_turns"), ("check_ms", "check_ms"), ("pr", "lab_pr"),
    ("event_id", "event_id"),
)


def _csv_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in {"=", "+", "-", "@", "\t", "\r"} else text


def export_records(rows: list[dict[str, Any]], redact_fn: Callable[[Any], tuple[str, list[str]]] | None = None) -> list[dict[str, Any]]:
    """Audit export rows: metadata columns only, detail redacted and masked, newest first."""
    rate = usd_rate()
    out = []
    for row in sorted(rows, key=lambda item: str(item.get("occurred_at") or ""), reverse=True):
        record: dict[str, Any] = {}
        for name, field in CSV_COLUMNS:
            if name == "control_point":
                record[name] = control_point(row)
            elif name == "detail":
                record[name] = re.sub(r"\s+", " ", mask(str(row.get("detail") or ""), redact_fn))[:200]
            elif name == "usd":
                record[name] = to_usd(row.get("lab_cost"), rate)
            else:
                record[name] = row.get(field or "")
        out.append(record)
    return out


def csv_rows(rows: list[dict[str, Any]], redact_fn: Callable[[Any], tuple[str, list[str]]] | None = None) -> list[list[str]]:
    records = export_records(rows, redact_fn)
    return [[name for name, _ in CSV_COLUMNS]] + [[_csv_cell(record[name]) for name, _ in CSV_COLUMNS] for record in records]
