"""Lab views: one board row per ticket and a simple ROI summary.

Both functions take the stored event rows (hook events and lab events) and
derive everything from them. Nothing here writes to storage.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


LAB_KINDS = ("pr_opened", "ci_result", "approved", "merged", "ticket_started", "ticket_done")
LAB_ROLES = ("participant", "ci-reviewer", "guide")
BUILD_TOOLS = {"write_file", "apply_diff", "execute_command"}
STATUS_ORDER = ("planning", "building", "pr_open", "merged")


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _minutes(start: str | None, end: str | None) -> float | None:
    first, last = _parse(start), _parse(end)
    if not first or not last:
        return None
    return round(max((last - first).total_seconds(), 0) / 60, 1)


def _is_plans_path(path: str | None) -> bool:
    normalized = "/" + str(path or "").replace("\\", "/").lstrip("./")
    return "/plans/" in normalized


def _is_participant(row: dict[str, Any]) -> bool:
    """Hook events from a participant. A missing role counts as participant."""
    return row.get("source") != "lab" and row.get("lab_role") in {None, "", "participant"}


def _lab_kind(row: dict[str, Any]) -> str | None:
    return row.get("lab_kind") if row.get("source") == "lab" else None


def lab_board(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one row per ticket.

    Status is the furthest stage reached:
      planning  - the first participant event (or ticket_started) on the ticket
      building  - the first participant PreToolUse of write_file, apply_diff or
                  execute_command whose file path is not under plans/
      pr_open   - a pr_opened lab event
      merged    - a merged lab event
    minutes   = merged_at (or the latest event) minus started_at.
    prompts   = participant UserPromptSubmit events.
    tool_calls = participant PreToolUse events.
    blocks    = blocked events on the ticket, any role.
    ci        = first ci_result verdict decides first_try_pass; verdict and
                findings come from the latest ci_result.
    cost_credits = Bobcoins on the ticket (X-Lab-Cost header), null if none.
                   A Stop event's cost is cumulative for its session, so it
                   counts only its increase over the session maximum so far
                   (see metrics.usage_deltas); other events count as sent.
    """
    from .metrics import usage_deltas

    ticket_costs: dict[str, list[float]] = defaultdict(list)
    for record in usage_deltas(rows):
        if record["ticket"] and record["bobcoins"] is not None:
            ticket_costs[str(record["ticket"])].append(record["bobcoins"])
    tickets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("lab_ticket"):
            tickets[str(row["lab_ticket"])].append(row)

    board = []
    for ticket, items in tickets.items():
        items.sort(key=lambda item: str(item.get("occurred_at") or ""))
        participant = [item for item in items if _is_participant(item)]
        started = next(
            (item for item in items if _is_participant(item) or _lab_kind(item) == "ticket_started"),
            None,
        )
        status_index = 0 if started else -1
        if any(
            item.get("hook_event") == "PreToolUse"
            and item.get("tool_name") in BUILD_TOOLS
            and not _is_plans_path(item.get("lab_path"))
            for item in participant
        ):
            status_index = max(status_index, 1)
        if any(_lab_kind(item) == "pr_opened" for item in items):
            status_index = max(status_index, 2)
        merged = next((item for item in items if _lab_kind(item) == "merged"), None)
        if merged:
            status_index = 3
        owner = started or next(
            (item for item in items if _lab_kind(item) in {"pr_opened", "merged"}), items[0]
        )
        ci_runs = [item for item in items if _lab_kind(item) == "ci_result"]
        first_ci = (ci_runs[0].get("lab_data") or {}) if ci_runs else None
        last_ci = (ci_runs[-1].get("lab_data") or {}) if ci_runs else None
        costs = ticket_costs.get(ticket, [])
        pr = next((item.get("lab_pr") for item in reversed(items) if item.get("lab_pr") is not None), None)
        merged_data = (merged.get("lab_data") or {}) if merged else {}
        started_at = started.get("occurred_at") if started else None
        merged_at = merged.get("occurred_at") if merged else None
        board.append({
            "ticket": ticket,
            "user": owner.get("user_name"),
            "status": STATUS_ORDER[status_index] if status_index >= 0 else "planning",
            "started_at": started_at,
            "merged_at": merged_at,
            "minutes": _minutes(started_at, merged_at or items[-1].get("occurred_at")),
            "prompts": sum(item.get("hook_event") == "UserPromptSubmit" for item in participant),
            "tool_calls": sum(item.get("hook_event") == "PreToolUse" for item in participant),
            "blocks": sum(item.get("decision") == "blocked" for item in items),
            "ci": {
                "first_try_pass": None if first_ci is None else first_ci.get("verdict") == "PASS",
                "verdict": None if last_ci is None else last_ci.get("verdict"),
                "findings": None if last_ci is None else last_ci.get("findings"),
                "runs": len(ci_runs),
            },
            "pr": pr,
            "approver": merged_data.get("approver"),
            "review_rounds": merged_data.get("review_rounds"),
            "lines_changed": merged_data.get("lines_changed"),
            "branch": next((item.get("lab_branch") for item in reversed(items) if item.get("lab_branch")), None),
            "cost_credits": round(sum(costs), 4) if costs else None,
        })
    return sorted(board, key=lambda row: row["ticket"])


def lab_roi(rows: list[dict[str, Any]], baseline_minutes: float = 240) -> dict[str, Any]:
    """Return per-ticket minutes against a manual baseline, plus totals.

    The math is deliberately simple:
      minutes_saved (per merged ticket) = baseline_minutes - minutes
      total minutes_saved              = sum over merged tickets
      pct_faster                       = minutes_saved / (baseline_minutes * merged) * 100
      blocks_before_merge              = blocked events on a ticket at or before
                                         its merge time (all blocks if not merged)
      cost_per_merged_pr               = sum of cost_credits on merged tickets /
                                         merged count, or null when any merged
                                         ticket has no cost data
      review                           = from ci_result events: share of PRs whose
                                         first CI run passed, and mean findings
                                         per PR on the latest run
    Unmerged tickets are listed but do not count toward saved minutes.
    """
    board = lab_board(rows)
    by_ticket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("lab_ticket"):
            by_ticket[str(row["lab_ticket"])].append(row)

    tickets = []
    blocks_before_merge = 0
    for entry in board:
        merged_at = entry["merged_at"]
        blocks = sum(
            item.get("decision") == "blocked"
            and (merged_at is None or str(item.get("occurred_at") or "") <= merged_at)
            for item in by_ticket[entry["ticket"]]
        )
        blocks_before_merge += blocks
        saved = (
            round(baseline_minutes - entry["minutes"], 1)
            if entry["status"] == "merged" and entry["minutes"] is not None
            else None
        )
        tickets.append({
            "ticket": entry["ticket"], "user": entry["user"], "status": entry["status"],
            "minutes": entry["minutes"], "baseline_minutes": baseline_minutes,
            "minutes_saved": saved, "blocks_before_merge": blocks,
            "cost_credits": entry["cost_credits"],
        })

    merged = [entry for entry in board if entry["status"] == "merged"]
    merged_minutes = round(sum(entry["minutes"] or 0 for entry in merged), 1)
    baseline_total = round(baseline_minutes * len(merged), 1)
    minutes_saved = round(baseline_total - merged_minutes, 1)
    pct_faster = round(minutes_saved / baseline_total * 100, 1) if baseline_total else None
    merged_costs = [entry["cost_credits"] for entry in merged]
    cost_per_pr = (
        round(sum(merged_costs) / len(merged_costs), 4)
        if merged_costs and all(cost is not None for cost in merged_costs)
        else None
    )
    with_ci = [entry for entry in board if entry["ci"]["first_try_pass"] is not None]
    first_try = sum(bool(entry["ci"]["first_try_pass"]) for entry in with_ci)
    findings = [entry["ci"]["findings"] for entry in with_ci if isinstance(entry["ci"]["findings"], (int, float))]

    if merged:
        headline = (
            f"{len(merged)} tickets merged in {merged_minutes:g} min against a "
            f"{baseline_total:g} min baseline ({pct_faster:g}% faster); "
            f"{blocks_before_merge} risky actions blocked before merge."
        )
    else:
        headline = f"No tickets merged yet; {blocks_before_merge} risky actions blocked so far."
    return {
        "baseline_minutes": baseline_minutes,
        "tickets": tickets,
        "totals": {
            "tickets": len(board),
            "tickets_merged": len(merged),
            "merged_minutes": merged_minutes,
            "baseline_minutes_total": baseline_total,
            "minutes_saved": minutes_saved,
            "pct_faster": pct_faster,
            "blocks_before_merge": blocks_before_merge,
            "cost_per_merged_pr": cost_per_pr,
        },
        "review": {
            "prs_with_ci": len(with_ci),
            "first_try_passes": first_try,
            "first_try_pass_rate_pct": round(first_try / len(with_ci) * 100, 1) if with_ci else None,
            "findings_per_pr": round(sum(findings) / len(findings), 2) if findings else None,
        },
        "headline": headline,
    }
