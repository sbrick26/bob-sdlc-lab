from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .storage import ObjectConflict, ObjectStoreUnavailable, ResilientObjectRepository, build_repository


ALLOWED_DECISIONS = {"allowed", "blocked", "observed", "error"}
ALLOWED_SEVERITIES = {"info", "medium", "high", "critical"}

FIELDS = (
    "event_id", "occurred_at", "user_name", "device_name", "device_id", "organization",
    "source", "delivery", "profile_name", "profile_id", "policy_version", "bob_version", "bob_channel",
    "hook_event", "decision", "rule_id", "rule_name", "severity", "workspace", "tool_name",
    "tool_category", "tool_use_id", "outcome", "duration_ms", "tool_duration_ms",
    "prompt_length_bucket", "response_length_bucket", "finding_count", "hook_status", "content_logged",
    "detail", "evidence", "prompt_content", "tool_input_content", "tool_output_content",
    "response_content", "session_id",
    # Lab fields: ticket, role, and branch headers from the lab hook client,
    # Bobcoins (X-Lab-Cost), context tokens and turns (cumulative per session on
    # Stop events), the edited file path, and lab (GitHub/CI) event data.
    "lab_ticket", "lab_role", "lab_branch", "lab_cost", "lab_path", "lab_kind", "lab_pr", "lab_data",
    "lab_tokens", "lab_turns",
    # Team (X-Governance-Team) and this server's processing time per hook call.
    "team", "check_ms", "session_source",
)

SORT_COLUMNS = {
    "time": "occurred_at", "user": "user_name", "device": "device_name", "profile": "profile_name",
    "source": "source", "event": "hook_event", "decision": "decision", "rule": "rule_id",
    "severity": "severity", "duration": "duration_ms",
}

_lock = threading.RLock()
_repository: ResilientObjectRepository | None = None
_events: dict[str, dict[str, Any]] = {}
_policies: dict[str, dict[str, Any] | None] = {"active": None, "draft": None}
_rollouts: dict[int, dict[str, Any]] = {}
_tool_starts: dict[str, int] = {}


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo() -> ResilientObjectRepository:
    global _repository
    if _repository is None:
        _repository = build_repository()
    return _repository


def _copy(value: dict[str, Any] | None) -> dict[str, Any] | None:
    return json.loads(json.dumps(value)) if value is not None else None


def _day(value: str | None) -> str:
    return str(value or utcnow())[:10].replace("-", "/")


def _event_key(event: dict[str, Any]) -> str:
    return f"events/by-time/{_day(event.get('occurred_at'))}/{event['event_id']}.json"


def init_db() -> None:
    """Load the optional in-process query index from the durable object repository."""
    repository = _repo()
    with _lock:
        _events.clear()
        for _, event in repository.list_json("events/by-time/"):
            if event.get("event_id"):
                _events[str(event["event_id"])] = event
        try:
            _policies["active"] = repository.get_json("policies/active.json")
            _policies["draft"] = repository.get_json("policies/draft.json")
        except ObjectStoreUnavailable:
            # A brief COS outage should not keep the API process from starting. The
            # managed endpoint hook retains its own last-known-good enforcement policy.
            _policies["active"] = _policies.get("active")
            _policies["draft"] = _policies.get("draft")
        _rollouts.clear()
        for key, rollout in repository.list_json("rollouts/"):
            if key.endswith("/current.json") and rollout.get("id") is not None:
                _rollouts[int(rollout["id"])] = rollout


def storage_health() -> dict[str, Any]:
    return _repo().health()


def flush_pending_writes(limit: int = 100) -> int:
    repository = _repo()
    flushed = repository.flush_pending(limit=limit)
    if repository.health()["status"] == "available":
        with _lock:
            active = repository.get_json("policies/active.json")
            draft = repository.get_json("policies/draft.json")
            if active is not None:
                _policies["active"] = active
            if draft is not None:
                _policies["draft"] = draft
    return flushed


def reset_repository_for_tests() -> None:
    global _repository
    with _lock:
        _repository = None
        _events.clear()
        _policies.update({"active": None, "draft": None})
        _rollouts.clear()
        _tool_starts.clear()


def _persist_policy(document: dict[str, Any], *, pointer: str, immutable_key: str) -> None:
    repository = _repo()
    repository.put_json_durable(immutable_key, document, immutable=True)
    repository.put_json_durable(pointer, document)


def ensure_policy(config: dict[str, Any], version: str) -> None:
    now = utcnow()
    with _lock:
        persist_defaults = not (
            _repo().mode == "cos" and _repo().health()["status"] == "degraded"
        )
        if _policies["active"] is None:
            active = {
                "id": version, "version": version, "status": "active", "revision": "1",
                "config": _copy(config), "created_by": "system", "created_at": now,
                "updated_at": now, "published_at": now,
            }
            if persist_defaults:
                _persist_policy(active, pointer="policies/active.json", immutable_key=f"policies/versions/{version}.json")
            _policies["active"] = active
        if _policies["draft"] is None:
            draft = {
                "id": f"draft-{version}", "version": f"draft-{version}", "status": "draft",
                "revision": "1", "config": _copy(config), "created_by": "system",
                "created_at": now, "updated_at": now, "published_at": None,
            }
            if persist_defaults:
                _persist_policy(draft, pointer="policies/draft.json", immutable_key=f"policies/drafts/{draft['id']}/1.json")
            _policies["draft"] = draft


def active_policy() -> dict[str, Any] | None:
    with _lock:
        return _copy(_policies["active"])


def draft_policy() -> dict[str, Any] | None:
    with _lock:
        return _copy(_policies["draft"])


def save_policy_draft(config: dict[str, Any], expected_revision: str, actor: str) -> dict[str, Any]:
    with _lock:
        current = _policies["draft"]
        if not current or current["revision"] != expected_revision:
            raise ValueError("draft revision conflict")
        revision = str(int(current["revision"]) + 1)
        updated = {
            **current, "revision": revision, "parent_revision": expected_revision,
            "config": _copy(config), "created_by": actor, "updated_at": utcnow(),
        }
        immutable_key = f"policies/drafts/{updated['id']}/{revision}.json"
        try:
            _repo().put_json_durable(immutable_key, updated, immutable=True)
        except ObjectConflict:
            # A prior request may have written the immutable revision and then lost
            # connectivity before advancing the pointer. Reuse only that exact edit.
            existing = _repo().get_json_durable(immutable_key)
            if not existing or existing.get("parent_revision") != expected_revision or existing.get("config") != updated.get("config"):
                raise
            updated = existing
        _repo().put_json_durable("policies/draft.json", updated)
        _policies["draft"] = updated
        return _copy(updated) or {}


def _rollout_id() -> int:
    candidate = time.time_ns() // 1_000
    while candidate in _rollouts:
        candidate += 1
    return candidate


def _persist_rollout(rollout: dict[str, Any]) -> dict[str, Any]:
    rollout_id = int(rollout["id"])
    revision = str(rollout["revision"])
    history_key = f"rollouts/{rollout_id}/history/{revision}.json"
    try:
        _repo().put_json_durable(history_key, rollout, immutable=True)
    except ObjectConflict:
        existing = _repo().get_json_durable(history_key)
        logical_fields = ("id", "revision", "policy_version", "status", "target_count", "error")
        if not existing or any(existing.get(field) != rollout.get(field) for field in logical_fields):
            raise
        rollout = existing
    _repo().put_json_durable(f"rollouts/{rollout_id}/current.json", rollout)
    return rollout


def publish_policy_draft(version: str, actor: str) -> tuple[dict[str, Any], int]:
    """Stage a durable release and rollout without changing the active policy.

    The existing name is retained for API compatibility. A successful MDM publish
    must be followed by ``finalize_policy_publication(...)`` after the MDM API
    accepts the profile update and group sync request. The rollout is then marked
    ``submitted`` because device acknowledgement is a separate lifecycle state.
    Failed/configuration-required transitions leave the prior active policy
    and editable draft unchanged.
    """
    with _lock:
        current = _policies["draft"]
        if not current:
            raise ValueError("no policy draft")
        now = utcnow()
        rollout_id = _rollout_id()
        candidate_key = f"policies/releases/{rollout_id}.json"
        candidate = {
            **current, "id": version, "version": version, "status": "staged", "created_by": actor,
            "updated_at": now, "published_at": None, "staged_at": now,
            "source_draft_id": current.get("id"), "source_draft_revision": current.get("revision"),
        }
        _repo().put_json_durable(candidate_key, candidate, immutable=True)
        rollout = {
            "id": rollout_id, "revision": "1", "policy_version": version, "status": "pending",
            "candidate_key": candidate_key, "source_draft_revision": current.get("revision"),
            "profile_id": os.environ.get("SIMPLEMDM_PROFILE_ID", "100001"),
            "assignment_group_id": os.environ.get("SIMPLEMDM_GROUP_ID", "200001"),
            "target_count": 0, "acknowledged_count": 0, "error": None,
            "started_at": now, "completed_at": None,
        }
        rollout = _persist_rollout(rollout)
        _rollouts[rollout_id] = rollout
        return _copy(candidate) or {}, rollout_id


def finalize_policy_publication(rollout_id: int, *, target_count: int = 0) -> dict[str, Any]:
    """Activate a staged policy after its managed profile has published successfully."""
    with _lock:
        current = _rollouts.get(rollout_id)
        if not current:
            raise ValueError("unknown rollout")
        if current.get("status") == "submitted":
            active = _policies.get("active")
            if active and active.get("version") == current.get("policy_version"):
                return _copy(active) or {}
        if current.get("status") != "pending":
            raise ValueError("rollout is not pending")
        candidate = _repo().get_json_durable(str(current["candidate_key"]))
        if not candidate:
            raise ObjectStoreUnavailable("staged policy release is missing")
        # The immutable version precedes the active pointer. An orphan version is
        # harmless if the pointer fails, and the same rollout can be retried.
        published = {
            **candidate, "status": "active", "published_at": candidate.get("staged_at"),
        }
        _persist_policy(
            published,
            pointer="policies/active.json",
            immutable_key=f"policies/versions/{published['version']}.json",
        )
        _policies["active"] = published
        updated = {
            **current, "revision": str(int(current["revision"]) + 1), "status": "submitted",
            "target_count": target_count, "error": None, "completed_at": utcnow(),
        }
        updated = _persist_rollout(updated)
        _rollouts[rollout_id] = updated
        return _copy(published) or {}


def update_rollout(rollout_id: int, status: str, *, target_count: int = 0, error: str | None = None) -> None:
    if status == "succeeded":
        finalize_policy_publication(rollout_id, target_count=target_count)
        return
    with _lock:
        current = _rollouts.get(rollout_id)
        if not current:
            raise ValueError("unknown rollout")
        updated = {
            **current, "revision": str(int(current["revision"]) + 1), "status": status,
            "target_count": target_count, "error": error,
            "completed_at": utcnow() if status in {"succeeded", "failed", "configuration_required"} else None,
        }
        updated = _persist_rollout(updated)
        _rollouts[rollout_id] = updated


def latest_rollout() -> dict[str, Any] | None:
    with _lock:
        return _copy(_rollouts[max(_rollouts)]) if _rollouts else None


def _persist_event_indexes(event: dict[str, Any]) -> None:
    repository = _repo()
    event_id = str(event["event_id"])
    day = _day(event.get("occurred_at"))
    reference = {
        "schema_version": 1, "event_id": event_id, "occurred_at": event.get("occurred_at"),
        "event_ref": _event_key(event), "decision": event.get("decision"), "rule_id": event.get("rule_id"),
    }
    user_hash = hashlib.sha256(str(event.get("user_name") or "unknown").encode()).hexdigest()[:24]
    rule_key = str(event.get("rule_id") or "no-rule").replace("/", "-")
    repository.put_json(f"indexes/users/{user_hash}/{day}/{event_id}.json", reference, immutable=True)
    repository.put_json(f"indexes/rules/{rule_key}/{day}/{event_id}.json", reference, immutable=True)


def _persist_outbox(event: dict[str, Any]) -> None:
    event_id = str(event["event_id"])
    _repo().put_json(
        f"outbox/pending/{event_id}.json",
        {
            "schema_version": 1, "event_id": event_id, "status": "pending",
            "created_at": event.get("ingested_at") or utcnow(), "event_ref": _event_key(event),
            "stream_key": event.get("organization") or event.get("device_id") or event_id,
            "metadata": {
                "occurred_at": event.get("occurred_at"), "tenant": event.get("organization"),
                "user_name": event.get("user_name"), "device_id": event.get("device_id"),
                "profile_id": event.get("profile_id"), "rule_id": event.get("rule_id"),
                "decision": event.get("decision"), "content_ref": event.get("content_ref"),
            },
        },
        immutable=True,
    )


def insert_event(event: dict[str, Any]) -> bool:
    event_id = str(event["event_id"])
    with _lock:
        if event_id in _events:
            # Repair auxiliary objects if a previous process stopped between the
            # immutable event write and its scan indexes/outbox write.
            _persist_event_indexes(_events[event_id])
            _persist_outbox(_events[event_id])
            return False
        document = {field: event.get(field) for field in FIELDS}
        document.update({
            "schema_version": 1,
            "kind": "governance.event",
            "ingested_at": utcnow(),
            "tenant": event.get("organization"),
            "content_ref": None,
        })
        content_fields = ("prompt_content", "tool_input_content", "tool_output_content", "response_content")
        content = {field: document.get(field) for field in content_fields if document.get(field) is not None}
        content_size = len(json.dumps(content, ensure_ascii=False).encode("utf-8"))
        if content and content_size > int(os.environ.get("COS_INLINE_CONTENT_MAX", "8192")):
            content_key = f"content/{_day(document.get('occurred_at'))}/{event_id}.json"
            _repo().put_json(content_key, {"schema_version": 1, "event_id": event_id, "content": content}, immutable=True)
            document["content_ref"] = content_key
            for field in content_fields:
                document[field] = None
        try:
            _repo().put_json(_event_key(document), document, immutable=True)
        except ObjectConflict:
            return False
        _persist_event_indexes(document)
        _persist_outbox(document)
        _events[event_id] = document
        return True


def _hydrate(row: dict[str, Any]) -> dict[str, Any]:
    result = _copy(row) or {}
    if result.get("content_ref"):
        try:
            content = _repo().get_json(str(result["content_ref"]))
            if content:
                result.update(content.get("content") or {})
        except ObjectStoreUnavailable:
            result["content_unavailable"] = True
    return result


def _filtered_events(filters: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = {
        "user": "user_name", "device": "device_name", "profile": "profile_name", "source": "source",
        "decision": "decision", "rule": "rule_id", "severity": "severity", "event": "hook_event", "tool": "tool_name",
        "ticket": "lab_ticket", "role": "lab_role", "session": "session_id",
    }
    with _lock:
        rows = list(_events.values())
    for key, field in mapping.items():
        if filters.get(key):
            rows = [row for row in rows if row.get(field) == filters[key]]
    since = str(filters.get("since") or "").strip()
    if since:
        rows = [row for row in rows if str(row.get("occurred_at") or "") >= since]
    until = str(filters.get("until") or "").strip()
    if until:
        # A date-only bound includes the whole day.
        width = 10 if len(until) == 10 else len(until)
        rows = [row for row in rows if str(row.get("occurred_at") or "")[:width] <= until]
    query = str(filters.get("q") or "").lower()
    if query:
        fields = ("detail", "workspace", "rule_name", "user_name", "device_name")
        rows = [row for row in rows if any(query in str(row.get(field) or "").lower() for field in fields)]
    return rows


def filtered_events(filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Every event that matches the filters, metadata and inline content, unsorted."""
    return [_copy(row) or {} for row in _filtered_events(filters)]


def query_events(filters: dict[str, Any], limit: int = 250, sort: str = "time", direction: str = "desc") -> list[dict[str, Any]]:
    column = SORT_COLUMNS.get(sort, "occurred_at")
    rows = _filtered_events(filters)
    rows.sort(key=lambda row: (row.get(column) is not None, row.get(column) or ""), reverse=direction.lower() != "asc")
    content_fields = {"prompt_content", "tool_input_content", "tool_output_content", "response_content", "content_ref"}
    return [
        {key: value for key, value in (_copy(row) or {}).items() if key not in content_fields}
        for row in rows[:min(max(limit, 1), 1000)]
    ]


def get_event(event_id: str) -> dict[str, Any] | None:
    """Return one event with investigation content hydrated on demand."""
    with _lock:
        event = _events.get(event_id)
    return _hydrate(event) if event else None


def facets() -> dict[str, list[str]]:
    columns = {
        "users": "user_name", "devices": "device_name", "profiles": "profile_name", "sources": "source",
        "decisions": "decision", "rules": "rule_id", "severities": "severity", "events": "hook_event", "tools": "tool_name",
        "tickets": "lab_ticket", "roles": "lab_role",
    }
    with _lock:
        rows = list(_events.values())
    return {name: sorted({str(row[column]) for row in rows if row.get(column) not in {None, ""}}) for name, column in columns.items()}


def summary() -> dict[str, Any]:
    with _lock:
        rows = list(_events.values())
    rule_counts: dict[tuple[str, str], int] = defaultdict(int)
    decisions: dict[str, int] = defaultdict(int)
    for row in rows:
        rule_counts[(row.get("rule_id") or "No violation", row.get("rule_name") or "Screened")] += 1
        decisions[str(row.get("decision"))] += 1
    rules = [{"rule_id": key[0], "rule_name": key[1], "count": count} for key, count in sorted(rule_counts.items(), key=lambda item: item[1], reverse=True)]
    return {
        "events": len(rows), "blocked": decisions.get("blocked", 0),
        "reporting_devices": len({row.get("device_name") for row in rows}),
        "last_event": max((str(row.get("occurred_at")) for row in rows), default=None),
        "rules": rules, "decisions": dict(decisions),
    }


def fleet() -> list[dict[str, Any]]:
    with _lock:
        rows = list(_events.values())
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("device_name") or "Unknown")].append(row)
    result = []
    for device_name, items in grouped.items():
        latest = max(items, key=lambda item: str(item.get("occurred_at") or ""))
        result.append({
            "device_name": device_name, "user_name": latest.get("user_name"), "profile_name": latest.get("profile_name"),
            "policy_version": latest.get("policy_version"), "bob_version": latest.get("bob_version"),
            "delivery": latest.get("delivery"), "last_seen": latest.get("occurred_at"), "event_count": len(items),
            "blocked_count": sum(item.get("decision") == "blocked" for item in items),
        })
    return sorted(result, key=lambda row: str(row.get("last_seen") or ""), reverse=True)


def _aggregate(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(items), "allowed": sum(item.get("decision") == "allowed" for item in items),
        "blocked": sum(item.get("decision") == "blocked" for item in items),
        "observed": sum(item.get("decision") == "observed" for item in items),
        "errors": sum(item.get("decision") == "error" for item in items),
    }


def _average(items: list[dict[str, Any]], field: str) -> tuple[float | None, int]:
    samples = [float(item[field]) for item in items if item.get(field) is not None]
    return (round(sum(samples) / len(samples), 1), len(samples)) if samples else (None, 0)


def analytics(days: int = 30, granularity: str = "auto") -> dict[str, Any]:
    days = min(max(int(days), 1), 90)
    resolved = "hour" if granularity == "auto" and days <= 2 else ("day" if granularity == "auto" else granularity)
    if resolved not in {"hour", "day"}:
        resolved = "day"
    effective_days = min(days, 7) if resolved == "hour" else days
    now_dt = datetime.now(timezone.utc)
    since_dt = now_dt - timedelta(days=effective_days)
    since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    with _lock:
        rows = [row for row in _events.values() if str(row.get("occurred_at") or "") >= since]

    overall = _aggregate(rows)
    enforceable = [row for row in rows if row.get("hook_event") in {"UserPromptSubmit", "PreToolUse"}]
    policy_avg, policy_samples = _average(rows, "duration_ms")
    tool_avg, tool_samples = _average(rows, "tool_duration_ms")
    overall.update({
        "enforceable_total": len(enforceable), "reporting_users": len({row.get("user_name") for row in rows}),
        "users_with_blocks": len({row.get("user_name") for row in rows if row.get("decision") == "blocked"}),
        "reporting_devices": len({row.get("device_name") for row in rows}),
        "active_rules": len({row.get("rule_id") for row in rows if row.get("rule_id")}),
        "avg_policy_duration_ms": policy_avg, "policy_duration_samples": policy_samples,
        "avg_tool_duration_ms": tool_avg, "tool_duration_samples": tool_samples,
        "last_event": max((str(row.get("occurred_at")) for row in rows), default=None),
        "blocked_rate_pct": round(overall["blocked"] / len(enforceable) * 100, 1) if enforceable else 0.0,
    })
    user_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        user_groups[str(row.get("user_name") or "Unknown")].append(row)
    top_users, rates = [], []
    for user, items in user_groups.items():
        item = {"user_name": user, **_aggregate(items)}
        user_enforceable = [entry for entry in items if entry.get("hook_event") in {"UserPromptSubmit", "PreToolUse"}]
        item["enforceable_total"] = len(user_enforceable)
        item["blocked_rate_pct"] = round(item["blocked"] / len(user_enforceable) * 100, 1) if user_enforceable else 0.0
        item["last_seen"] = max(str(entry.get("occurred_at") or "") for entry in items)
        rates.append(item["blocked_rate_pct"])
        top_users.append(item)
    top_users.sort(key=lambda item: (-item["total"], -item["blocked"], item["user_name"]))
    overall["highest_user_block_rate_pct"] = max(rates, default=0.0)

    step = timedelta(hours=1) if resolved == "hour" else timedelta(days=1)
    cursor = since_dt.replace(minute=0, second=0, microsecond=0) if resolved == "hour" else since_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now_dt.replace(minute=0, second=0, microsecond=0) if resolved == "hour" else now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    timeline = []
    while cursor <= end:
        bucket = cursor.strftime("%Y-%m-%dT%H:00:00Z") if resolved == "hour" else cursor.strftime("%Y-%m-%d")
        bucket_rows = [row for row in rows if str(row.get("occurred_at") or "").startswith(bucket[:13] if resolved == "hour" else bucket)]
        timeline.append({"bucket": bucket, **_aggregate(bucket_rows)})
        cursor += step

    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for field in ("hook_event", "rule_id", "tool_name"):
        values: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if row.get(field) not in {None, ""}:
                values[str(row[field])].append(row)
        groups[field] = values
    hook_events = []
    for name, items in groups["hook_event"].items():
        average, _ = _average(items, "duration_ms")
        hook_events.append({"hook_event": name, **_aggregate(items), "avg_policy_duration_ms": average})
    hook_events.sort(key=lambda item: (-item["total"], item["hook_event"]))
    rules = []
    for rule_id, items in groups["rule_id"].items():
        agg = _aggregate(items)
        rules.append({
            "rule_id": rule_id, "rule_name": items[-1].get("rule_name"), "severity": items[-1].get("severity"),
            "total": agg["total"], "blocked": agg["blocked"], "observed": agg["observed"],
            "affected_users": len({item.get("user_name") for item in items}),
            "last_seen": max(str(item.get("occurred_at") or "") for item in items),
        })
    rules.sort(key=lambda item: (-item["total"], item["rule_id"]))
    tools = []
    for tool_name, items in groups["tool_name"].items():
        average, samples = _average(items, "tool_duration_ms")
        agg = _aggregate(items)
        tools.append({
            "tool_name": tool_name, "event_count": len(items),
            "tool_uses": len({item.get("tool_use_id") for item in items if item.get("tool_use_id")}),
            "blocked": agg["blocked"], "observed": agg["observed"],
            "avg_tool_duration_ms": average, "duration_samples": samples,
            "last_seen": max(str(item.get("occurred_at") or "") for item in items),
        })
    tools.sort(key=lambda item: (-item["event_count"], item["tool_name"]))
    return {
        "generated_at": utcnow(),
        "window": {"requested_days": days, "effective_days": effective_days, "since": since, "granularity": resolved},
        "overall": overall, "timeline": timeline, "top_users": top_users[:12],
        "hook_events": hook_events[:20], "rules": rules[:20], "tools": tools[:20],
    }


def all_events() -> list[dict[str, Any]]:
    with _lock:
        return [_copy(row) or {} for row in _events.values()]


def seed(events: list[dict[str, Any]]) -> int:
    return sum(1 for event in events if insert_event(event))


def start_tool(tool_use_id: str, started_ms: int) -> None:
    with _lock:
        _tool_starts[tool_use_id] = started_ms


def finish_tool(tool_use_id: str, ended_ms: int) -> int | None:
    with _lock:
        started_ms = _tool_starts.pop(tool_use_id, None)
    return None if started_ms is None else max(0, ended_ms - started_ms)
