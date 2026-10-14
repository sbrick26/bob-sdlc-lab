"""One summary per dashboard page, scoped by date range and team.

Every summary takes all stored rows and a Scope:
  since, until  local dates (YYYY-MM-DD), both inclusive, in the viewer's time
                zone (tz_offset = JavaScript getTimezoneOffset(), minutes behind UTC)
  team          one team name, or None for all teams

Usage (Bobcoins, context tokens, turns) is cumulative per session, so the
deltas are computed on the full history first and then cut to the window
(see metrics.usage_deltas). KPI deltas compare the window with the prior
window of the same length that ends the day before `since`.
"""

from __future__ import annotations

import json
import math
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable

from . import lab
from .metrics import (
    CI_LABEL, _is_hook, _lab_kind, _parse, _round, _sum, control_point, excerpt, is_ci,
    rules_summary, to_usd, usage_deltas, usd_rate, usd_rate_basis, violation_rows,
)

TEAM_DEFAULT = "unassigned"
OUTLIER_TOKENS = 150_000
OUTLIER_TURNS = 40
OUTLIER_BOBCOINS = 3.0
NEAR_LIMIT_PCT = 80.0
TOOL_TIMEOUT_MINUTES = 10
HANDS_ON_GAP_MINUTES = 15


# ---------------------------------------------------------------- scope

@dataclass(frozen=True)
class Scope:
    since: date | None = None
    until: date | None = None
    team: str | None = None
    tz_offset: int = 0

    @classmethod
    def parse(cls, since: str | None, until: str | None, team: str | None, tz_offset: int = 0) -> "Scope":
        """Raise ValueError for a malformed date or an inverted range."""
        first = date.fromisoformat(since) if since else None
        last = date.fromisoformat(until) if until else None
        if first and last and last < first:
            raise ValueError("until is before since")
        return cls(first, last, (team or "").strip() or None, int(tz_offset))

    def today(self) -> date:
        return (datetime.now(timezone.utc) - timedelta(minutes=self.tz_offset)).date()

    def last_day(self) -> date | None:
        return self.until or (self.today() if self.since else None)

    def _utc(self, day: date) -> datetime:
        return datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(minutes=self.tz_offset)

    def start(self) -> datetime | None:
        return self._utc(self.since) if self.since else None

    def end(self) -> datetime | None:
        last = self.until
        return self._utc(last + timedelta(days=1)) if last else None

    def contains(self, value: Any) -> bool:
        parsed = _parse(value)
        if parsed is None:
            return False
        start, end = self.start(), self.end()
        return (start is None or parsed >= start) and (end is None or parsed < end)

    def days(self) -> int | None:
        last = self.last_day()
        return (last - self.since).days + 1 if self.since and last else None

    def prior(self) -> "Scope | None":
        length = self.days()
        if not length or not self.since:
            return None
        return replace(self, since=self.since - timedelta(days=length), until=self.since - timedelta(days=1))

    def local_day(self, value: Any) -> date | None:
        parsed = _parse(value)
        return (parsed - timedelta(minutes=self.tz_offset)).date() if parsed else None

    def utc_bounds(self) -> tuple[str | None, str | None]:
        """ISO strings for filtering stored events: since inclusive, until exclusive."""
        start, end = self.start(), self.end()
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        return (start.strftime(fmt) if start else None, end.strftime(fmt) if end else None)


# ---------------------------------------------------------------- teams

def with_teams(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy rows and set `team` on each.

    A person's hook events carry X-Governance-Team. CI and lab events take the
    team of the ticket's owner (the first person to work on the ticket).
    """
    rows = sorted((dict(row) for row in rows), key=lambda row: str(row.get("occurred_at") or ""))
    user_team: dict[str, str] = {}
    owner: dict[str, str] = {}
    for row in rows:
        user = row.get("user_name")
        if _is_hook(row) and not is_ci(row) and user:
            if row.get("team") and row["team"] != TEAM_DEFAULT:
                user_team[user] = row["team"]
            if row.get("lab_ticket"):
                owner.setdefault(row["lab_ticket"], user)
    for row in rows:
        if row.get("lab_ticket") and _lab_kind(row) in {"ticket_started", "pr_opened"} and row.get("user_name"):
            owner.setdefault(row["lab_ticket"], row["user_name"])
    for row in rows:
        own = row.get("team") if row.get("team") and row.get("team") != TEAM_DEFAULT else None
        if _is_hook(row) and not is_ci(row):
            row["team"] = own or user_team.get(row.get("user_name") or "") or TEAM_DEFAULT
        else:
            ticket_owner = owner.get(row.get("lab_ticket") or "")
            row["team"] = (user_team.get(ticket_owner) if ticket_owner else None) or own or TEAM_DEFAULT
    return rows


def team_map(rows: Iterable[dict[str, Any]]) -> dict[str, str]:
    return {str(row.get("event_id")): row["team"] for row in with_teams(rows)}


# ---------------------------------------------------------------- math helpers

def percentile(values: list[float], pct: float) -> float | None:
    """Linear interpolation between closest ranks (the numpy default)."""
    clean = sorted(value for value in values if value is not None and math.isfinite(value))
    if not clean:
        return None
    rank = (len(clean) - 1) * pct / 100
    low, high = math.floor(rank), math.ceil(rank)
    return round(clean[low] + (clean[high] - clean[low]) * (rank - low), 3)


def delta_pct(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior == 0:
        return None
    return round((current - prior) / abs(prior) * 100, 1)


def _ratio(numerator: float | None, denominator: float | None, digits: int = 4) -> float | None:
    if numerator is None or not denominator:
        return None
    return round(numerator / denominator, digits)


def _seconds_between(start: Any, end: Any) -> float | None:
    first, last = _parse(start), _parse(end)
    return None if not first or not last else max((last - first).total_seconds(), 0.0)


def hands_on_minutes(times: list[Any], gap_minutes: float = HANDS_ON_GAP_MINUTES) -> float | None:
    """Sum of gaps between consecutive events; a gap over `gap_minutes` counts as 0."""
    parsed = sorted(value for value in (_parse(item) for item in times) if value)
    if not parsed:
        return None
    total = 0.0
    for first, second in zip(parsed, parsed[1:]):
        gap = (second - first).total_seconds() / 60
        if gap <= gap_minutes:
            total += gap
    return round(total, 1)


# ---------------------------------------------------------------- data for one scope

class View:
    """The rows, usage deltas and tickets of one scope."""

    def __init__(self, rows: list[dict[str, Any]], scope: Scope, annotated: bool = False):
        self.scope = scope
        self.rate = usd_rate()
        everything = rows if annotated else with_teams(rows)
        self.all_rows = everything
        self.rows = [row for row in everything if not scope.team or row["team"] == scope.team]
        self.deltas = usage_deltas(self.rows)
        self.board = lab.lab_board(self.rows)
        self.ticket_team = {}
        for row in self.rows:
            if row.get("lab_ticket"):
                self.ticket_team.setdefault(row["lab_ticket"], row["team"])
        self.tickets = self._tickets()
        self.win = [row for row in self.rows if scope.contains(row.get("occurred_at"))]
        self.win_deltas = [record for record in self.deltas if scope.contains(record["occurred_at"])]
        self.hooks = [row for row in self.win if _is_hook(row)]
        self.people_hooks = [row for row in self.hooks if not is_ci(row)]

    def _tickets(self) -> list[dict[str, Any]]:
        by_ticket: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self.rows:
            if row.get("lab_ticket"):
                by_ticket[str(row["lab_ticket"])].append(row)
        coins: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in self.deltas:
            if record["ticket"]:
                coins[str(record["ticket"])].append(record)
        result = []
        for entry in self.board:
            items = sorted(by_ticket[entry["ticket"]], key=lambda item: str(item.get("occurred_at") or ""))
            pr_opened = next((item for item in items if _lab_kind(item) == "pr_opened"), None)
            pr_opened_at = pr_opened.get("occurred_at") if pr_opened else None
            bobcoins = _round(_sum(coins[entry["ticket"]], "bobcoins"))
            tokens = _sum(coins[entry["ticket"]], "tokens")
            # Hands-on: participant events from the first prompt to PR opened (or the last event).
            people = [item for item in items if _is_hook(item) and not is_ci(item)]
            first_prompt = next((item.get("occurred_at") for item in people if item.get("hook_event") == "UserPromptSubmit"), None)
            stop_at = str(pr_opened_at or "9999")
            span = [item.get("occurred_at") for item in people
                    if first_prompt and first_prompt <= str(item.get("occurred_at") or "") <= stop_at]
            if pr_opened_at and first_prompt:
                span.append(pr_opened_at)
            hands_on = hands_on_minutes(span)
            hands_on_h = round(hands_on / 60, 2) if hands_on is not None else None
            result.append({
                "ticket": entry["ticket"], "user": entry["user"], "team": self.ticket_team.get(entry["ticket"], TEAM_DEFAULT),
                "status": entry["status"], "started_at": entry["started_at"], "pr_opened_at": pr_opened_at,
                "merged_at": entry["merged_at"],
                "minutes_to_pr": lab._minutes(entry["started_at"], pr_opened_at) if pr_opened_at else None,
                "minutes_to_merge": lab._minutes(entry["started_at"], entry["merged_at"]) if entry["merged_at"] else None,
                "bobcoins": bobcoins, "usd": to_usd(bobcoins, self.rate),
                "tokens": None if tokens is None else int(tokens),
                "verdict": entry["ci"]["verdict"], "findings": entry["ci"]["findings"],
                "first_try_pass": entry["ci"]["first_try_pass"], "pr": entry["pr"], "blocks": entry["blocks"],
                "hands_on_hours": hands_on_h,
            })
        return result

    # tickets that touch the window
    def window_tickets(self) -> list[dict[str, Any]]:
        return [
            ticket for ticket in self.tickets
            if any(self.scope.contains(ticket[key]) for key in ("started_at", "pr_opened_at", "merged_at"))
        ]

    def merged(self) -> list[dict[str, Any]]:
        return [ticket for ticket in self.tickets if ticket["merged_at"] and self.scope.contains(ticket["merged_at"])]

    def reviewed(self) -> list[dict[str, Any]]:
        return [
            ticket for ticket in self.tickets
            if ticket["first_try_pass"] is not None and ticket["pr_opened_at"] and self.scope.contains(ticket["pr_opened_at"])
        ]

    def granularity(self) -> str:
        """Up to 31 days: daily buckets; up to 183: ISO weeks; beyond: months."""
        count = len(self.day_list())
        return "day" if count <= 31 else ("week" if count <= 183 else "month")

    def bucket(self, day: date) -> date:
        granularity = self.granularity()
        if granularity == "week":
            return day - timedelta(days=day.weekday())
        if granularity == "month":
            return day.replace(day=1)
        return day

    def buckets(self) -> list[date]:
        return list(dict.fromkeys(self.bucket(day) for day in self.day_list()))

    def bucket_of(self, value: Any) -> str | None:
        day = self.scope.local_day(value)
        return self.bucket(day).isoformat() if day else None

    def day_list(self) -> list[date]:
        """Every local day in the window, or the days the data spans."""
        if getattr(self, "_days", None) is not None:
            return self._days
        last = self.scope.last_day()
        if self.scope.since and last:
            first = self.scope.since
            self._days = [first + timedelta(days=offset) for offset in range((last - first).days + 1)]
            return self._days
        else:
            days = [day for day in (self.scope.local_day(row.get("occurred_at")) for row in self.win) if day]
            if not days:
                return []
            first, last = min(days), max(days)
        self._days = [first + timedelta(days=offset) for offset in range((last - first).days + 1)]
        return self._days

    def people(self) -> list[str]:
        return sorted({row["user_name"] for row in self.people_hooks if row.get("user_name")})

    def sessions(self, rows: list[dict[str, Any]]) -> int:
        return len({row.get("session_id") for row in rows if row.get("session_id") not in {None, "", "unknown"}})

    def daily_active(self) -> list[dict[str, Any]]:
        per_day: dict[date, set[str]] = defaultdict(set)
        for row in self.people_hooks:
            day = self.scope.local_day(row.get("occurred_at"))
            if day and row.get("user_name"):
                per_day[day].add(row["user_name"])
        # Average daily active users per bucket (a day, a week or a month).
        groups: dict[date, list[int]] = defaultdict(list)
        for day in self.day_list():
            groups[self.bucket(day)].append(len(per_day.get(day, set())))
        return [{"day": bucket.isoformat(), "people": round(sum(values) / len(values), 2)} for bucket, values in groups.items()]


# ---------------------------------------------------------------- KPIs with deltas

def _kpis(view: View) -> dict[str, float | None]:
    merged = view.merged()
    merged_minutes = [ticket["minutes_to_merge"] for ticket in merged if ticket["minutes_to_merge"] is not None]
    merged_coins = [ticket["bobcoins"] for ticket in merged if ticket["bobcoins"] is not None]
    reviewed = view.reviewed()
    passed = sum(bool(ticket["first_try_pass"]) for ticket in reviewed)
    daily = view.daily_active()
    coins = _round(_sum(view.win_deltas, "bobcoins"))
    perf = _performance_numbers(view)
    return {
        "bobcoins": coins,
        "usd": to_usd(coins, view.rate),
        # Fully loaded: every Bobcoin in the range (unmerged work and CI review too) per merged PR.
        "bobcoins_per_merged_pr": round(coins / len(merged), 4) if merged and coins is not None else None,
        "bobcoins_per_merged_pr_direct": round(sum(merged_coins) / len(merged), 4) if merged and merged_coins else None,
        "prs_merged": len(merged),
        "prs_opened": sum(1 for ticket in view.tickets if ticket["pr_opened_at"] and view.scope.contains(ticket["pr_opened_at"])),
        "daily_active_people": round(sum(item["people"] for item in daily) / len(daily), 2) if daily else None,
        "active_people": len(view.people()),
        "sessions": view.sessions(view.people_hooks),
        "median_minutes_to_merge": round(statistics.median(merged_minutes), 1) if merged_minutes else None,
        "blocked": sum(row.get("decision") == "blocked" for row in view.win),
        # Violations: every rule hit, blocked or flagged.
        "violations": len(violation_rows(view.win)),
        "flagged": sum(row.get("decision") == "observed" and bool(row.get("rule_id")) for row in view.win),
        "first_try_pass_rate_pct": round(passed / len(reviewed) * 100, 1) if reviewed else None,
        "tokens": _sum(view.win_deltas, "tokens"),
        **perf,
    }


def kpis_with_deltas(rows: list[dict[str, Any]], scope: Scope) -> tuple[View, dict[str, dict[str, Any]], int | None]:
    annotated = with_teams(rows)
    view = View(annotated, scope, annotated=True)
    current = _kpis(view)
    prior_scope = scope.prior()
    prior = _kpis(View(annotated, prior_scope, annotated=True)) if prior_scope else {}
    has_prior = bool(prior_scope) and any(
        row for row in annotated
        if (not scope.team or row["team"] == scope.team) and prior_scope.contains(row.get("occurred_at"))
    )
    out = {
        key: {"value": value, "prior": prior.get(key) if has_prior else None,
              "delta_pct": delta_pct(value, prior.get(key)) if has_prior else None}
        for key, value in current.items()
    }
    return view, out, scope.days()


def _common(view: View, kpis: dict[str, Any], period_days: int | None) -> dict[str, Any]:
    teams = sorted({row["team"] for row in view.all_rows if _is_hook(row) and not is_ci(row)})
    return {
        "usd_rate": view.rate, "usd_rate_basis": usd_rate_basis(view.rate),
        "teams": teams, "period_days": period_days,
        "scope": {
            "since": view.scope.since.isoformat() if view.scope.since else None,
            "until": view.scope.last_day().isoformat() if view.scope.last_day() else None,
            "team": view.scope.team,
        },
        "kpis": kpis, "ci_label": CI_LABEL,
        "jira_base_url": (os.environ.get("JIRA_BASE_URL") or "").strip().rstrip("/") or None,
    }


# ---------------------------------------------------------------- budgets

def budget_config() -> dict[str, Any]:
    """LAB_BUDGETS, e.g. {"teams": {"Platform": 100}, "default_person": 50, "period": "month"}."""
    try:
        raw = json.loads(os.environ.get("LAB_BUDGETS") or "{}")
    except ValueError:
        raw = {}
    raw = raw if isinstance(raw, dict) else {}
    teams = {str(name): float(value) for name, value in (raw.get("teams") or {}).items() if isinstance(value, (int, float)) and value > 0}
    people = {str(name): float(value) for name, value in (raw.get("people") or {}).items() if isinstance(value, (int, float)) and value > 0}
    default_person = raw.get("default_person")
    return {
        "teams": teams, "people": people,
        "default_person": float(default_person) if isinstance(default_person, (int, float)) and default_person > 0 else None,
        "period": "month",
    }


def _month_scope(scope: Scope) -> Scope:
    """Budgets are monthly: always the 1st of the current month to today, whatever the date range."""
    today = scope.today()
    return Scope(today.replace(day=1), today, scope.team, scope.tz_offset)


def _days_in_month(first: date) -> int:
    following = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return (following - first).days


def burn_level(pct: float | None) -> str | None:
    """Thresholds: 50, 80 and 100 percent of the budget."""
    if pct is None:
        return None
    if pct >= 100:
        return "over"
    if pct >= NEAR_LIMIT_PCT:
        return "near"
    if pct >= 50:
        return "half"
    return "under"


def budgets(view: View) -> dict[str, Any]:
    config = budget_config()
    month = _month_scope(view.scope)
    in_month = [record for record in view.deltas if month.contains(record["occurred_at"])]
    team_spend: dict[str, float] = defaultdict(float)
    person_spend: dict[str, float] = defaultdict(float)
    for record in in_month:
        if record["bobcoins"] is None:
            continue
        team_spend[record["team"] or TEAM_DEFAULT] += record["bobcoins"]
        if not record["ci"] and record["user"]:
            person_spend[record["user"]] += record["bobcoins"]

    def entry(kind: str, name: str, spent: float, budget: float | None, team: str | None = None) -> dict[str, Any]:
        pct = round(spent / budget * 100, 1) if budget else None
        return {
            "kind": kind, "name": name, "team": team, "bobcoins": round(spent, 4), "budget": budget,
            "pct": pct, "left": round(budget - spent, 4) if budget else None, "level": burn_level(pct),
            "usd": to_usd(round(spent, 4), view.rate),
        }

    teams = [
        entry("team", name, team_spend.get(name, 0.0), budget)
        for name, budget in sorted(config["teams"].items())
        if not view.scope.team or name == view.scope.team
    ]
    person_team = {row["user_name"]: row["team"] for row in view.rows if _is_hook(row) and not is_ci(row) and row.get("user_name")}
    people = [
        entry("person", user, spent, config["people"].get(user, config["default_person"]), person_team.get(user))
        for user, spent in sorted(person_spend.items())
    ]
    near = sorted(
        (item for item in teams + people if item["pct"] is not None and item["pct"] >= NEAR_LIMIT_PCT),
        key=lambda item: -item["pct"],
    )
    total_budget = sum(item["budget"] for item in teams if item["budget"])
    total_spent = sum(item["bobcoins"] for item in teams)
    return {
        "period": "month", "month_start": month.since.isoformat(), "month_end": month.until.isoformat(),
        "teams": teams, "people": people, "near_limit": near,
        # Budget used = Bobcoins spent this month (all spend on the team's tickets,
        # CI review included) / sum of the monthly team budgets in scope.
        "used_pct": round(total_spent / total_budget * 100, 1) if total_budget else None,
        "used_bobcoins": round(total_spent, 4) if total_budget else None,
        "total_budget": total_budget or None,
        # Daily pace: the monthly budgets in scope spread evenly over the days of the month.
        "daily_pace": round(total_budget / _days_in_month(month.since), 4) if total_budget else None,
        "thresholds": [50, 80, 100],
    }


# ---------------------------------------------------------------- performance numbers

def _tool_pairs(view: View) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pair PreToolUse with the next PostToolUse of the same tool_use_id.

    Returns (completed pairs, failures). A failure is an allowed PreToolUse
    with no PostToolUse within 10 minutes. A PreToolUse younger than 10
    minutes and still open is neither.
    """
    posts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in view.rows:
        if row.get("hook_event") == "PostToolUse" and row.get("tool_use_id"):
            posts[row["tool_use_id"]].append(row)
    now = datetime.now(timezone.utc)
    pairs, failures = [], []
    for row in view.hooks:
        if row.get("hook_event") != "PreToolUse" or row.get("decision") == "blocked" or not row.get("tool_use_id"):
            continue
        started = _parse(row.get("occurred_at"))
        if not started:
            continue
        match = next(
            (post for post in sorted(posts.get(row["tool_use_id"], []), key=lambda item: str(item.get("occurred_at") or ""))
             if (_parse(post.get("occurred_at")) or started) >= started
             and _seconds_between(row.get("occurred_at"), post.get("occurred_at")) <= TOOL_TIMEOUT_MINUTES * 60),
            None,
        )
        if match:
            measured = match.get("tool_duration_ms")
            seconds = measured / 1000 if measured is not None else _seconds_between(row.get("occurred_at"), match.get("occurred_at"))
            pairs.append({"tool": row.get("tool_name") or "unknown", "seconds": seconds, "at": row.get("occurred_at")})
        elif (now - started).total_seconds() > TOOL_TIMEOUT_MINUTES * 60:
            failures.append({"tool": row.get("tool_name") or "unknown", "at": row.get("occurred_at"),
                             "user": row.get("user_name"), "ticket": row.get("lab_ticket")})
    return pairs, failures


def tool_outcomes(rows: list[dict[str, Any]]) -> dict[str, str]:
    """Outcome of each PreToolUse: "blocked", "completed" (a PostToolUse within 10 minutes) or "failed".

    A PreToolUse younger than 10 minutes with no PostToolUse yet has no outcome.
    """
    posts: dict[str, list[datetime]] = defaultdict(list)
    for row in rows:
        if row.get("hook_event") == "PostToolUse" and row.get("tool_use_id"):
            parsed = _parse(row.get("occurred_at"))
            if parsed:
                posts[row["tool_use_id"]].append(parsed)
    now = datetime.now(timezone.utc)
    result: dict[str, str] = {}
    for row in rows:
        if row.get("hook_event") != "PreToolUse":
            continue
        if row.get("decision") == "blocked":
            result[str(row.get("event_id"))] = "blocked"
            continue
        started = _parse(row.get("occurred_at"))
        if not started:
            continue
        done = any(started <= end <= started + timedelta(minutes=TOOL_TIMEOUT_MINUTES) for end in posts.get(row.get("tool_use_id") or "", []))
        if done:
            result[str(row.get("event_id"))] = "completed"
        elif (now - started).total_seconds() > TOOL_TIMEOUT_MINUTES * 60:
            result[str(row.get("event_id"))] = "failed"
    return result


def _turns(view: View) -> list[dict[str, Any]]:
    """Turn = first UserPromptSubmit after the previous Stop, to the next Stop, per session."""
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in view.rows:
        if row.get("hook_event") in {"UserPromptSubmit", "Stop"} and row.get("session_id") not in {None, "", "unknown"}:
            by_session[row["session_id"]].append(row)
    turns = []
    for items in by_session.values():
        items.sort(key=lambda item: str(item.get("occurred_at") or ""))
        start = None
        for row in items:
            if row.get("hook_event") == "UserPromptSubmit":
                start = start or row
            elif start is not None:
                if view.scope.contains(row.get("occurred_at")):
                    turns.append({"seconds": _seconds_between(start.get("occurred_at"), row.get("occurred_at")), "at": row.get("occurred_at")})
                start = None
    return turns


def _performance_numbers(view: View) -> dict[str, float | None]:
    pairs, failures = _tool_pairs(view)
    turns = _turns(view)
    checks = [float(row["check_ms"]) for row in view.hooks if row.get("check_ms") is not None]
    rtt = [float(row["hook_rtt_prev_ms"]) for row in view.hooks if row.get("hook_rtt_prev_ms") is not None]
    attempts = len(pairs) + len(failures)
    return {
        "rtt_p50_ms": percentile(rtt, 50),
        "rtt_p95_ms": percentile(rtt, 95),
        "tool_success_pct": round(len(pairs) / attempts * 100, 1) if attempts else None,
        "tool_p50_s": percentile([pair["seconds"] for pair in pairs], 50),
        "tool_p95_s": percentile([pair["seconds"] for pair in pairs], 95),
        "turn_p50_s": percentile([turn["seconds"] for turn in turns], 50),
        "turn_p95_s": percentile([turn["seconds"] for turn in turns], 95),
        "check_p50_ms": percentile(checks, 50),
        "check_p95_ms": percentile(checks, 95),
        "tool_failure_rate_pct": round(len(failures) / attempts * 100, 1) if attempts else None,
    }


# ---------------------------------------------------------------- scaling: top N and Other

TOP_N = 10
TOP_TEAMS = 8
MIN_ACTIONS = 20
MIN_PRS = 3


def top_n(items: list[dict[str, Any]], value: str, label: str, n: int = TOP_N, other: str = "Other") -> dict[str, Any]:
    """The top `n` items by `value` (ties alphabetical) plus one summed "Other (N)" row."""
    ordered = sorted(items, key=lambda item: (-(item.get(value) or 0), str(item.get(label))))
    head, tail = ordered[:n], ordered[n:]
    if tail:
        summed = {key: sum(item.get(key) or 0 for item in tail) for key, sample in tail[0].items() if isinstance(sample, (int, float)) and not isinstance(sample, bool)}
        head = head + [{**summed, label: f"{other} ({len(tail)})", "other": True, "count": len(tail)}]
    return {"items": head, "total": len(items), "truncated": bool(tail)}


def _fold_teams(spend: dict[tuple[str, str], float], n: int = TOP_TEAMS) -> dict[tuple[str, str], float]:
    """Keep the top `n` teams by total spend; fold the rest into "Other"."""
    totals: dict[str, float] = defaultdict(float)
    for (_, team), value in spend.items():
        totals[team] += value
    keep = {team for team, _ in sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:n]}
    folded: dict[tuple[str, str], float] = defaultdict(float)
    for (bucket, team), value in spend.items():
        folded[(bucket, team if team in keep else "Other")] += value
    return dict(folded)


# ---------------------------------------------------------------- per-team table and merge times

def team_table(view: View) -> list[dict[str, Any]]:
    """One row per team (users' teams, not "unassigned"), each computed in the same scope."""
    teams = sorted({row["team"] for row in view.all_rows if _is_hook(row) and not is_ci(row)} - {TEAM_DEFAULT})
    if view.scope.team:
        teams = [team for team in teams if team == view.scope.team]
    config = budget_config()["teams"]
    result = []
    for team in teams:
        team_view = View(view.all_rows, replace(view.scope, team=team), annotated=True)
        numbers = _kpis(team_view)
        month = budgets(team_view)
        burn = next((item for item in month["teams"] if item["name"] == team), None)
        result.append({
            "team": team, "users": numbers["active_people"],
            "bobcoins": numbers["bobcoins"], "usd": numbers["usd"],
            "budget": config.get(team), "budget_used_pct": burn["pct"] if burn else None,
            "budget_bobcoins": burn["bobcoins"] if burn else None,
            "budget_level": burn["level"] if burn else None,
            "prs_merged": numbers["prs_merged"], "median_minutes_to_merge": numbers["median_minutes_to_merge"],
            "violations": numbers["violations"], "first_try_pass_rate_pct": numbers["first_try_pass_rate_pct"],
        })
    return result


def merge_median_per_day(view: View) -> list[dict[str, Any]]:
    per_day: dict[str, list[float]] = defaultdict(list)
    for ticket in view.merged():
        bucket = view.bucket_of(ticket["merged_at"])
        if bucket and ticket["minutes_to_merge"] is not None:
            per_day[bucket].append(ticket["minutes_to_merge"])
    return [
        {"day": bucket.isoformat(), "minutes": round(statistics.median(per_day[bucket.isoformat()]), 1) if per_day.get(bucket.isoformat()) else None,
         "merged": len(per_day.get(bucket.isoformat(), []))}
        for bucket in view.buckets()
    ]


MERGE_BUCKETS = (("Under 1 h", 0, 60), ("1-2 h", 60, 120), ("2-4 h", 120, 240), ("4-8 h", 240, 480),
                 ("8-24 h", 480, 1440), ("1-2 days", 1440, 2880), ("Over 2 days", 2880, math.inf))


def _merge_by_team(view: View, merged: list[dict[str, Any]]) -> dict[str, Any]:
    """Median minutes from ticket start to merge, per team."""
    groups: dict[str, list[float]] = defaultdict(list)
    for ticket in merged:
        if ticket["minutes_to_merge"] is not None:
            groups[ticket["team"]].append(ticket["minutes_to_merge"])
    items = [{"team": team, "minutes": round(statistics.median(values), 1), "merged": len(values)} for team, values in groups.items()]
    return top_n(items, "merged", "team") | {"items": sorted(top_n(items, "merged", "team")["items"], key=lambda item: (-(item.get("minutes") or 0), item["team"]))}


def _cost_per_pr_by_team(view: View, merged: list[dict[str, Any]]) -> dict[str, Any]:
    """Fully loaded Bobcoins per merged PR per team; teams with fewer than 3 merged PRs are not ranked."""
    merged_count: dict[str, int] = defaultdict(int)
    for ticket in merged:
        merged_count[ticket["team"]] += 1
    spend: dict[str, float] = defaultdict(float)
    for record in view.win_deltas:
        if record["bobcoins"]:
            spend[record["team"] or TEAM_DEFAULT] += record["bobcoins"]
    items = [
        {"team": team, "bobcoins_per_pr": round(spend.get(team, 0.0) / count, 4), "merged": count,
         "usd_per_pr": to_usd(round(spend.get(team, 0.0) / count, 4), view.rate)}
        for team, count in merged_count.items() if count >= MIN_PRS
    ]
    result = top_n(items, "bobcoins_per_pr", "team")
    if result["truncated"]:
        result["items"] = result["items"][:-1]
    result.update({"unranked": sum(1 for count in merged_count.values() if count < MIN_PRS), "min_prs": MIN_PRS})
    return result


def merge_distribution(view: View) -> list[dict[str, Any]]:
    minutes = [ticket["minutes_to_merge"] for ticket in view.merged() if ticket["minutes_to_merge"] is not None]
    return [{"bucket": label, "count": sum(1 for value in minutes if low <= value < high)} for label, low, high in MERGE_BUCKETS]


def _team_violations(view: View) -> list[dict[str, Any]]:
    counts: dict[str, int] = defaultdict(int)
    for row in view.win:
        if row.get("rule_id") and row.get("decision") in {"blocked", "observed"}:
            counts[row["team"]] += 1
    return [{"team": team, "violations": count} for team, count in sorted(counts.items())]


# ---------------------------------------------------------------- page summaries

def overview(rows: list[dict[str, Any]], scope: Scope) -> dict[str, Any]:
    view, kpis, days = kpis_with_deltas(rows, scope)
    budget = budgets(view)
    kpis["budget_used_pct"] = {"value": budget["used_pct"], "prior": None, "delta_pct": None}
    kpis["budget_used_bobcoins"] = {"value": budget["used_bobcoins"], "prior": None, "delta_pct": None}
    kpis["budget_total"] = {"value": budget["total_budget"], "prior": None, "delta_pct": None}
    spend: dict[tuple[str, str], float] = defaultdict(float)
    for record in view.win_deltas:
        bucket = view.bucket_of(record["occurred_at"])
        if bucket and record["bobcoins"] is not None:
            spend[(bucket, record["team"] or TEAM_DEFAULT)] += record["bobcoins"]
    spend = _fold_teams(spend)
    rules: dict[str, dict[str, Any]] = {}
    for row in violation_rows(view.win):
        entry = rules.setdefault(row["rule_id"], {"rule_id": row["rule_id"], "rule_name": row.get("rule_name"), "severity": row.get("severity"), "blocked": 0, "observed": 0, "violations": 0})
        entry[row["decision"]] += 1
        entry["violations"] += 1
    return {
        **_common(view, kpis, days),
        "days": [bucket.isoformat() for bucket in view.buckets()],
        "granularity": view.granularity(),
        "spend_by_team": [{"day": day, "team": team, "bobcoins": round(value, 4)} for (day, team), value in sorted(spend.items())],
        "daily_active": view.daily_active(),
        "by_team": team_table(view),
        "violations_by_team": top_n(_team_violations(view), "violations", "team"),
        "merge_median_per_day": merge_median_per_day(view),
        "violations_by_rule": top_n(list(rules.values()), "violations", "rule_id"),
    }


def _session_totals(view: View) -> dict[str, dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for record in view.deltas:
        entry = totals.setdefault(record["session"], {
            "session": record["session"], "user": record["user"], "ticket": record["ticket"], "team": record["team"],
            "ci": record["ci"], "bobcoins": 0.0, "tokens": 0.0, "turns": 0.0, "active": False,
        })
        for key in ("bobcoins", "tokens", "turns"):
            if record[key] is not None:
                entry[key] += record[key]
        entry["ticket"] = entry["ticket"] or record["ticket"]
        entry["active"] = entry["active"] or view.scope.contains(record["occurred_at"])
    return totals


def outliers(view: View) -> list[dict[str, Any]]:
    """Sessions active in the window with context tokens > 150,000, turns > 40 or Bobcoins > 3."""
    result = []
    for entry in _session_totals(view).values():
        if not entry["active"]:
            continue
        flags = []
        if entry["tokens"] > OUTLIER_TOKENS:
            flags.append("context tokens")
        if entry["turns"] > OUTLIER_TURNS:
            flags.append("turns")
        if entry["bobcoins"] > OUTLIER_BOBCOINS:
            flags.append("Bobcoins")
        if flags:
            result.append({
                "session": str(entry["session"])[:8], "session_id": entry["session"],
                "user": CI_LABEL if entry["ci"] else entry["user"],
                "ticket": entry["ticket"], "team": entry["team"], "bobcoins": round(entry["bobcoins"], 4),
                "usd": to_usd(round(entry["bobcoins"], 4), view.rate), "tokens": int(entry["tokens"]),
                "turns": int(entry["turns"]), "flags": flags,
            })
    return sorted(result, key=lambda item: -item["bobcoins"])


def _equation(view: View) -> dict[str, float | None]:
    """People spend = active people x sessions per person x turns per session x Bobcoins per turn."""
    deltas = [record for record in view.win_deltas if not record["ci"]]
    ci = [record for record in view.win_deltas if record["ci"]]
    people = len(view.people())
    sessions = view.sessions(view.people_hooks)
    turns = _sum(deltas, "turns")
    coins = _sum(deltas, "bobcoins")
    return {
        "active_people": people,
        "sessions_per_person": _ratio(sessions, people, 4),
        "turns_per_session": _ratio(turns, sessions, 4),
        "bobcoins_per_turn": _ratio(coins, turns, 6),
        "people_bobcoins": _round(coins),
        "ci_bobcoins": _round(_sum(ci, "bobcoins")),
        # Same number as the Overview "Bobcoin spend" for the same filters.
        "total_bobcoins": _round(_sum(view.win_deltas, "bobcoins")),
        "bobcoins_per_user": _ratio(coins, people, 4),
    }


def cost(rows: list[dict[str, Any]], scope: Scope) -> dict[str, Any]:
    view, kpis, days = kpis_with_deltas(rows, scope)
    budget = budgets(view)
    equation = _equation(view)
    prior_scope = scope.prior()
    prior_eq = _equation(View(view.all_rows, prior_scope, annotated=True)) if prior_scope else {}
    has_prior = bool(prior_scope) and any(kpis[key]["prior"] is not None for key in ("bobcoins", "sessions", "active_people"))
    person_budget = {item["name"]: item for item in budget["people"]}
    people = []
    for user in view.people():
        mine = [row for row in view.people_hooks if row.get("user_name") == user]
        my = [record for record in view.win_deltas if record["user"] == user and not record["ci"]]
        coins = _round(_sum(my, "bobcoins"))
        people.append({
            "user": user, "team": next((row["team"] for row in mine), TEAM_DEFAULT),
            "sessions": view.sessions(mine),
            "turns": None if _sum(my, "turns") is None else int(_sum(my, "turns")),
            "bobcoins": coins, "usd": to_usd(coins, view.rate),
            "tokens": None if _sum(my, "tokens") is None else int(_sum(my, "tokens")),
            "budget_pct": person_budget.get(user, {}).get("pct"),
            "budget": person_budget.get(user, {}).get("budget"),
            "budget_bobcoins": person_budget.get(user, {}).get("bobcoins"),
        })
    ci_hooks = [row for row in view.hooks if is_ci(row)]
    ci_deltas = [record for record in view.win_deltas if record["ci"]]
    automation = None
    if ci_hooks or ci_deltas:
        coins = _round(_sum(ci_deltas, "bobcoins"))
        automation = {
            "label": CI_LABEL, "sessions": view.sessions(ci_hooks),
            "turns": None if _sum(ci_deltas, "turns") is None else int(_sum(ci_deltas, "turns")),
            "bobcoins": coins, "usd": to_usd(coins, view.rate),
            "tokens": None if _sum(ci_deltas, "tokens") is None else int(_sum(ci_deltas, "tokens")),
        }
    # Spend per local day and team, plus each day's month-to-date total (all teams in scope).
    per_day_team: dict[tuple[str, str], float] = defaultdict(float)
    per_day: dict[date, float] = defaultdict(float)
    for record in view.deltas:
        day = scope.local_day(record["occurred_at"])
        if day and record["bobcoins"]:
            per_day[day] += record["bobcoins"]
            if scope.contains(record["occurred_at"]):
                per_day_team[(view.bucket(day).isoformat(), record["team"] or TEAM_DEFAULT)] += record["bobcoins"]
    per_day_team = _fold_teams(per_day_team)
    last_day_of: dict[date, date] = {}
    for day in view.day_list():
        last_day_of[view.bucket(day)] = day
    daily = []
    for bucket, last in last_day_of.items():
        month_to_date = sum(value for key, value in per_day.items() if key.year == last.year and key.month == last.month and key <= last)
        teams = {team: round(value, 4) for (key, team), value in per_day_team.items() if key == bucket.isoformat()}
        daily.append({"day": bucket.isoformat(), "teams": teams, "total": round(sum(teams.values()), 4),
                      "month_to_date": round(month_to_date, 4)})
    return {
        **_common(view, kpis, days),
        "budgets": budget,
        "equation": {
            key: {"value": value, "prior": prior_eq.get(key) if has_prior else None,
                  "delta_pct": delta_pct(value, prior_eq.get(key)) if has_prior else None}
            for key, value in equation.items()
        },
        "people": people, "automation": automation, "outliers": outliers(view),
        "by_team": team_table(view),
        "outlier_thresholds": {"tokens": OUTLIER_TOKENS, "turns": OUTLIER_TURNS, "bobcoins": OUTLIER_BOBCOINS},
        "daily": daily, "granularity": view.granularity(),
    }


def delivery(rows: list[dict[str, Any]], scope: Scope) -> dict[str, Any]:
    view, kpis, days = kpis_with_deltas(rows, scope)
    tickets = view.window_tickets()
    merged = view.merged()
    per_day = {bucket.isoformat(): {"day": bucket.isoformat(), "opened": 0, "merged": 0} for bucket in view.buckets()}
    for ticket in view.tickets:
        for key, field in (("opened", "pr_opened_at"), ("merged", "merged_at")):
            if ticket[field] and scope.contains(ticket[field]):
                bucket = view.bucket_of(ticket[field])
                if bucket in per_day:
                    per_day[bucket][key] += 1
    merged_coins = [ticket["bobcoins"] for ticket in merged if ticket["bobcoins"] is not None]
    reviewed = view.reviewed()
    return {
        **_common(view, kpis, days),
        "tickets": tickets,
        "merge_by_team": _merge_by_team(view, merged),
        "cost_per_pr_by_team": _cost_per_pr_by_team(view, merged),
        "prs_per_day": list(per_day.values()), "granularity": view.granularity(),
        "merge_distribution": merge_distribution(view),
        "by_team": team_table(view),
        "roi": roi(view, merged, reviewed, kpis),
    }


def _mean(values: list[float]) -> float | None:
    clean = [value for value in values if value is not None]
    return round(sum(clean) / len(clean), 1) if clean else None


def roi(view: View, merged: list[dict[str, Any]], reviewed: list[dict[str, Any]], kpis: dict[str, Any]) -> dict[str, Any]:
    """Delivery tiles: average time to PR and to merge, fully loaded Bobcoins per merged PR, first-try CI."""
    opened = [ticket for ticket in view.tickets if ticket["pr_opened_at"] and view.scope.contains(ticket["pr_opened_at"])]
    coins = kpis["bobcoins"]["value"]
    passed = sum(bool(ticket["first_try_pass"]) for ticket in reviewed)
    return {
        "merged": len(merged), "opened": len(opened),
        "avg_minutes_to_pr": _mean([ticket["minutes_to_pr"] for ticket in opened]),
        "avg_minutes_to_merge": _mean([ticket["minutes_to_merge"] for ticket in merged]),
        "bobcoins_total": coins, "usd_total": to_usd(coins, view.rate),
        "bobcoins_per_merged_pr": kpis["bobcoins_per_merged_pr"]["value"],
        "usd_per_merged_pr": to_usd(kpis["bobcoins_per_merged_pr"]["value"], view.rate),
        "bobcoins_per_merged_pr_direct": kpis["bobcoins_per_merged_pr_direct"]["value"],
        "ci_with_result": len(reviewed), "ci_first_try_passed": passed,
        "first_try_pass_rate_pct": round(passed / len(reviewed) * 100, 1) if reviewed else None,
    }


DEFAULT_PERF_TARGETS = {"answer_s": 120.0, "governance_ms": 1000.0, "tool_success_pct": 95.0}


def perf_targets() -> dict[str, float]:
    """PERF_TARGETS JSON, e.g. {"answer_s": 120, "governance_ms": 1000, "tool_success_pct": 95}."""
    try:
        raw = json.loads(os.environ.get("PERF_TARGETS") or "{}")
    except ValueError:
        raw = {}
    targets = dict(DEFAULT_PERF_TARGETS)
    if isinstance(raw, dict):
        targets.update({key: float(value) for key, value in raw.items() if key in targets and isinstance(value, (int, float))})
    return targets


def perf_status(typical: float | None, slow: float | None, target: float, higher_is_better: bool = False) -> str | None:
    """green: the typical value meets the target and so does the slow tail; amber: only the tail misses; red: typical misses."""
    if typical is None:
        return None
    meets = (lambda value: value >= target) if higher_is_better else (lambda value: value <= target)
    if not meets(typical):
        return "red"
    if slow is not None and not meets(slow):
        return "amber"
    return "green"


def _stats(values: list[float]) -> dict[str, float | int | None]:
    return {"p50": percentile(values, 50), "p95": percentile(values, 95), "p99": percentile(values, 99), "samples": len(values)}


def performance(rows: list[dict[str, Any]], scope: Scope) -> dict[str, Any]:
    view, kpis, days = kpis_with_deltas(rows, scope)
    targets = perf_targets()
    pairs, failures = _tool_pairs(view)
    turns = _turns(view)
    answer = [turn["seconds"] for turn in turns]
    rtt = [float(row["hook_rtt_prev_ms"]) for row in view.hooks if row.get("hook_rtt_prev_ms") is not None]
    checks = [float(row["check_ms"]) for row in view.hooks if row.get("check_ms") is not None]
    attempts = len(pairs) + len(failures)
    success = round(len(pairs) / attempts * 100, 1) if attempts else None

    by_tool: dict[str, list[float]] = defaultdict(list)
    for pair in pairs:
        by_tool[pair["tool"]].append(pair["seconds"])
    failed_by_tool: dict[str, int] = defaultdict(int)
    for failure in failures:
        failed_by_tool[failure["tool"]] += 1
    tools = []
    for tool in set(by_tool) | set(failed_by_tool):
        runs = len(by_tool.get(tool, [])) + failed_by_tool.get(tool, 0)
        tools.append({
            "tool": tool, "runs": runs, "failures": failed_by_tool.get(tool, 0),
            "success_pct": round(len(by_tool.get(tool, [])) / runs * 100, 1) if runs else None,
            "typical_s": percentile(by_tool.get(tool, []), 50), **{f"{key}_s": value for key, value in _stats(by_tool.get(tool, [])).items() if key != "samples"},
        })
    tools = top_n(tools, "runs", "tool")

    series = []
    worst_day_success = None
    for bucket in view.buckets():
        key = bucket.isoformat()
        day_answer = [turn["seconds"] for turn in turns if view.bucket_of(turn["at"]) == key]
        day_pairs = sum(1 for pair in pairs if view.bucket_of(pair["at"]) == key)
        day_failures = sum(1 for failure in failures if view.bucket_of(failure["at"]) == key)
        day_rtt = [float(row["hook_rtt_prev_ms"]) for row in view.hooks if row.get("hook_rtt_prev_ms") is not None and view.bucket_of(row.get("occurred_at")) == key]
        day_success = round(day_pairs / (day_pairs + day_failures) * 100, 1) if day_pairs + day_failures else None
        if day_success is not None:
            worst_day_success = day_success if worst_day_success is None else min(worst_day_success, day_success)
        series.append({
            "day": key, "answer_typical_s": percentile(day_answer, 50), "answer_slow_s": percentile(day_answer, 95), "answers": len(day_answer),
            "tool_success_pct": day_success, "tool_runs": day_pairs + day_failures,
            "governance_typical_ms": percentile(day_rtt, 50), "governance_slow_ms": percentile(day_rtt, 95),
        })
    answer_stats, rtt_stats = _stats(answer), _stats(rtt)
    return {
        **_common(view, kpis, days),
        "targets": targets,
        "cards": {
            "answer": {"typical_s": answer_stats["p50"], "slow_s": answer_stats["p95"],
                       "status": perf_status(answer_stats["p50"], answer_stats["p95"], targets["answer_s"])},
            "governance": {"typical_ms": rtt_stats["p50"], "slow_ms": rtt_stats["p95"],
                           "status": perf_status(rtt_stats["p50"], rtt_stats["p95"], targets["governance_ms"])},
            "tools": {"success_pct": success, "worst_day_pct": worst_day_success, "runs": attempts,
                      "status": perf_status(success, worst_day_success, targets["tool_success_pct"], higher_is_better=True)},
        },
        "tools": tools,
        "series": series, "granularity": view.granularity(),
        "engineering": {
            "answer_s": answer_stats, "server_check_ms": _stats(checks), "client_round_trip_ms": rtt_stats,
            "tools": sorted(({"tool": tool, **_stats(values)} for tool, values in by_tool.items()), key=lambda item: -(item["samples"] or 0)),
        },
        "failures": sorted(failures, key=lambda item: str(item["at"]), reverse=True)[:50],
    }


ACTION_EVENTS = {"PreToolUse", "UserPromptSubmit"}


def block_numbers(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Violations (rule hits, blocked or flagged), violation rate (per 100 actions; actions =
    PreToolUse + UserPromptSubmit), users affected, and repeat violations (user and rule pairs
    hit 2 or more times)."""
    actions = [row for row in rows if _is_hook(row) and row.get("hook_event") in ACTION_EVENTS]
    found = violation_rows(rows)
    pairs: dict[tuple[str, str], int] = defaultdict(int)
    for row in found:
        pairs[(str(row.get("user_name")), str(row.get("rule_id")))] += 1
    return {
        "violations": len(found),
        "violation_rate": round(len(found) / len(actions) * 100, 2) if actions else None,
        "users_affected": len({row.get("user_name") for row in found if not is_ci(row)}),
        "repeat_violations": sum(1 for count in pairs.values() if count >= 2),
    }


def violations(rows: list[dict[str, Any]], scope: Scope, redact_fn: Callable[[Any], tuple[str, list[str]]] | None = None, limit: int = 500) -> dict[str, Any]:
    view, kpis, days = kpis_with_deltas(rows, scope)
    current = block_numbers(view.win)
    prior_scope = scope.prior()
    prior_view = View(view.all_rows, prior_scope, annotated=True) if prior_scope else None
    prior = block_numbers(prior_view.win) if prior_view and prior_view.win else {}
    block_kpis = {
        key: {"value": value, "prior": prior.get(key), "delta_pct": delta_pct(value, prior.get(key)) if prior else None}
        for key, value in current.items()
    }
    found = sorted(violation_rows(view.win), key=lambda row: str(row.get("occurred_at") or ""), reverse=True)
    by_rule: dict[str, dict[str, Any]] = {}
    by_user: dict[str, int] = defaultdict(int)
    by_team: dict[str, int] = defaultdict(int)
    for row in found:
        entry = by_rule.setdefault(row["rule_id"], {"rule_id": row["rule_id"], "rule_name": row.get("rule_name"), "severity": row.get("severity"), "violations": 0})
        entry["violations"] += 1
        by_user[CI_LABEL if is_ci(row) else str(row.get("user_name") or "unknown")] += 1
        by_team[row["team"]] += 1
    actions_by_user: dict[str, int] = defaultdict(int)
    for row in view.people_hooks:
        if row.get("hook_event") in ACTION_EVENTS:
            actions_by_user[str(row.get("user_name"))] += 1
    ranked = [
        {"user": user, "violations": by_user.get(user, 0), "actions": count, "violation_rate": round(by_user.get(user, 0) / count * 100, 2)}
        for user, count in actions_by_user.items() if count >= MIN_ACTIONS
    ]
    unranked = sum(1 for count in actions_by_user.values() if 0 < count < MIN_ACTIONS)
    rate = top_n(ranked, "violation_rate", "user")
    if rate["truncated"]:
        other = rate["items"][-1]
        other["violation_rate"] = round(other["violations"] / other["actions"] * 100, 2) if other.get("actions") else 0.0
    rate.update({"unranked": unranked, "min_actions": MIN_ACTIONS})
    over_time = {bucket.isoformat(): 0 for bucket in view.buckets()}
    for row in found:
        bucket = view.bucket_of(row.get("occurred_at"))
        if bucket in over_time:
            over_time[bucket] += 1
    return {
        **_common(view, {**kpis, **block_kpis}, days),
        "by_rule": top_n(list(by_rule.values()), "violations", "rule_id"),
        "by_user": top_n([{"user": user, "violations": count} for user, count in by_user.items()], "violations", "user"),
        "violations_by_team": top_n([{"team": team, "violations": count} for team, count in by_team.items()], "violations", "team"),
        "rate_by_user": rate,
        "over_time": [{"day": day, "violations": count} for day, count in over_time.items()], "granularity": view.granularity(),
        "rows": [
            {
                "event_id": row.get("event_id"), "occurred_at": row.get("occurred_at"),
                "user": row.get("user_name"), "team": row["team"], "ticket": row.get("lab_ticket"),
                "rule_id": row.get("rule_id"), "rule_name": row.get("rule_name"),
                "control_point": control_point(row), "excerpt": excerpt(row, redact_fn),
                "decision": row.get("decision"),
            }
            for row in found[:limit]
        ],
    }


def rules(rows: list[dict[str, Any]], scope: Scope, catalog: dict[str, dict[str, Any]], enabled: dict[str, bool]) -> dict[str, Any]:
    view = View(rows, scope)
    return rules_summary(view.win, catalog, enabled)


def session_summary(rows: list[dict[str, Any]], session_id: str, tz_offset: int = 0) -> dict[str, Any] | None:
    """One Bob session: who, when, totals, and Bobcoins per turn from the Stop events' cumulative cost."""
    annotated = with_teams(rows)
    items = sorted((row for row in annotated if row.get("session_id") == session_id), key=lambda row: str(row.get("occurred_at") or ""))
    if not items:
        return None
    rate = usd_rate()
    deltas = usage_deltas(items)
    turns = per_turn(items)
    coins = _round(_sum(deltas, "bobcoins"))
    first, last = items[0].get("occurred_at"), items[-1].get("occurred_at")
    people = [row for row in items if not is_ci(row)]
    owner = people[0] if people else items[0]
    return {
        "session_id": session_id, "short_id": session_id[:8],
        "user": CI_LABEL if is_ci(owner) else owner.get("user_name"), "team": owner.get("team"),
        "ticket": next((row.get("lab_ticket") for row in items if row.get("lab_ticket")), None),
        "started_at": first, "ended_at": last,
        "duration_minutes": lab._minutes(first, last),
        "turns": None if _sum(deltas, "turns") is None else int(_sum(deltas, "turns")),
        "bobcoins": coins, "usd": to_usd(coins, rate),
        "tokens": None if _sum(deltas, "tokens") is None else int(_sum(deltas, "tokens")),
        "violations": len(violation_rows(items)),
        "events": len(items), "per_turn": turns, "usd_rate": rate,
    }


def per_turn(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bobcoins added at each Stop event of one session (its cumulative cost minus the highest earlier value)."""
    result, best = [], 0.0
    stops = [row for row in sorted(items, key=lambda row: str(row.get("occurred_at") or "")) if row.get("hook_event") == "Stop"]
    for index, row in enumerate(stops, start=1):
        value = row.get("lab_cost")
        added = None
        if value is not None:
            added = round(max(0.0, float(value) - best), 4)
            best = max(best, float(value))
        result.append({"index": index, "occurred_at": row.get("occurred_at"), "bobcoins": added,
                       "turns": row.get("lab_turns"), "tokens": row.get("lab_tokens")})
    return result
