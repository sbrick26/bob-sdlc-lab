import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="bob-governance-summaries-test-"))
os.environ.setdefault("INGEST_TOKEN", "test-ingest-token")
os.environ.setdefault("DASHBOARD_USER", "governance")
os.environ.setdefault("DASHBOARD_PASSWORD", "test-dashboard-password")

from fastapi.testclient import TestClient

from app import db, detail, summaries
from app.main import app
from app.policies import POLICY_VERSION, default_policy_config
from app.summaries import Scope

TOKEN = os.environ["INGEST_TOKEN"]
AUTH = (os.environ["DASHBOARD_USER"], os.environ["DASHBOARD_PASSWORD"])
client = TestClient(app)
db.init_db()
db.ensure_policy(default_policy_config(), POLICY_VERSION)


def row(time, event="UserPromptSubmit", user="sam", team="Platform", ticket="T-1", session="s1", **extra):
    return {
        "event_id": f"{user}-{session}-{event}-{time}", "source": "mdm-enforced-hook", "hook_event": event,
        "decision": "allowed", "user_name": user, "team": team, "lab_ticket": ticket, "session_id": session,
        "occurred_at": time, **extra,
    }


def lab_row(time, kind, ticket="T-1", user="sam", **data):
    return {"event_id": f"lab-{ticket}-{kind}-{time}", "source": "lab", "lab_kind": kind, "hook_event": f"lab.{kind}",
            "decision": "allowed", "user_name": user, "lab_ticket": ticket, "occurred_at": time, "lab_data": data}


def hook(event, user, ticket, session="s-1", headers=None, **payload):
    base = {"Authorization": f"Bearer {TOKEN}", "X-Governance-User": user, "X-Governance-Device": f"{user}-laptop",
            "X-Lab-Ticket": ticket, "X-Lab-Role": "participant", **(headers or {})}
    body = {"hook_event_name": event, "session_id": session, "cwd": "/work/lab", **payload}
    return client.post("/api/v1/hooks", headers=base, json=body)


# ---------------------------------------------------------------- scope, teams, deltas

def test_date_and_team_filtering():
    rows = [
        row("2026-03-02T10:00:00Z", "Stop", lab_cost=2.0),
        row("2026-03-02T11:00:00Z", "Stop", user="jordan", team="Field Apps", ticket="T-2", session="s2", lab_cost=5.0),
        row("2026-03-10T10:00:00Z", "Stop", session="s3", lab_cost=7.0),
    ]
    week = Scope.parse("2026-03-01", "2026-03-07", None, 0)
    assert summaries.overview(rows, week)["kpis"]["bobcoins"]["value"] == 7.0
    platform = Scope.parse("2026-03-01", "2026-03-07", "Platform", 0)
    assert summaries.overview(rows, platform)["kpis"]["bobcoins"]["value"] == 2.0
    assert summaries.overview(rows, Scope())["kpis"]["bobcoins"]["value"] == 14.0
    assert summaries.overview(rows, week)["teams"] == ["Field Apps", "Platform"]


def test_lab_and_ci_rows_take_the_ticket_owner_team():
    rows = [
        row("2026-03-02T10:00:00Z", team="Field Apps", user="jordan", ticket="T-9"),
        {**row("2026-03-02T11:00:00Z", "Stop", user="ci-reviewer", team=None, ticket="T-9", session="ci"), "lab_role": "ci-reviewer", "lab_cost": 1.0},
        lab_row("2026-03-02T12:00:00Z", "merged", ticket="T-9", user="guide"),
    ]
    teams = {item["event_id"]: item["team"] for item in summaries.with_teams(rows)}
    assert set(teams.values()) == {"Field Apps"}


def test_prior_period_delta():
    rows = [
        row("2026-03-01T10:00:00Z", "Stop", session="old", lab_cost=4.0),
        row("2026-03-08T10:00:00Z", "Stop", session="new", lab_cost=5.0),
    ]
    scope = Scope.parse("2026-03-08", "2026-03-14", None, 0)
    assert scope.prior() == Scope.parse("2026-03-01", "2026-03-07", None, 0)
    kpi = summaries.overview(rows, scope)["kpis"]["bobcoins"]
    assert (kpi["value"], kpi["prior"], kpi["delta_pct"]) == (5.0, 4.0, 25.0)
    # No prior data: no delta.
    lone = summaries.overview(rows, Scope.parse("2026-03-01", "2026-03-07", None, 0))["kpis"]["bobcoins"]
    assert lone["delta_pct"] is None
    assert summaries.delta_pct(5, 0) is None


# ---------------------------------------------------------------- budgets and outliers

def test_budget_burn_and_near_limit(monkeypatch):
    monkeypatch.setenv("LAB_BUDGETS", json.dumps({"teams": {"Platform": 100, "Field Apps": 100}, "default_person": 50, "period": "month"}))
    rows = [
        row("2026-03-02T10:00:00Z", "Stop", user="priya", session="p", lab_cost=42.0),
        row("2026-03-02T11:00:00Z", "Stop", user="sam", session="s", lab_cost=10.0),
        row("2026-03-03T10:00:00Z", "Stop", user="jordan", team="Field Apps", ticket="T-2", session="j", lab_cost=25.0),
        row("2026-02-20T10:00:00Z", "Stop", user="sam", session="feb", lab_cost=90.0),  # last month: not counted
    ]
    monkeypatch.setattr(summaries.Scope, "today", lambda self: summaries.date(2026, 3, 7))
    budget = summaries.cost(rows, Scope.parse("2026-03-01", "2026-03-07", None, 0))["budgets"]
    teams = {item["name"]: item for item in budget["teams"]}
    assert teams["Platform"]["pct"] == 52.0 and teams["Platform"]["level"] == "half"
    assert teams["Field Apps"]["pct"] == 25.0 and teams["Field Apps"]["level"] == "under"
    assert [(item["kind"], item["name"], item["pct"], item["left"]) for item in budget["near_limit"]] == [("person", "priya", 84.0, 8.0)]
    assert budget["used_pct"] == 38.5
    assert [summaries.burn_level(value) for value in (49.9, 50, 79.9, 80, 99.9, 100)] == ["under", "half", "half", "near", "near", "over"]
    monkeypatch.setenv("LAB_BUDGETS", "not json")
    assert summaries.cost(rows, Scope())["budgets"]["used_pct"] is None


def test_outlier_flags():
    rows = [
        row("2026-03-02T10:00:00Z", "Stop", session="big", lab_cost=3.5, lab_tokens=160_000, lab_turns=41),
        row("2026-03-02T11:00:00Z", "Stop", session="ok", lab_cost=1.0, lab_tokens=20_000, lab_turns=5),
        row("2026-03-02T12:00:00Z", "Stop", session="tokens", lab_cost=1.0, lab_tokens=150_001, lab_turns=5),
    ]
    found = {item["session"]: item["flags"] for item in summaries.cost(rows, Scope())["outliers"]}
    assert found == {"big": ["context tokens", "turns", "Bobcoins"], "tokens": ["context tokens"]}


# ---------------------------------------------------------------- performance

def test_percentiles_with_paired_tool_events():
    assert summaries.percentile([1, 2, 3, 4], 50) == 2.5
    assert summaries.percentile([1, 2, 3, 4], 95) == 3.85
    assert summaries.percentile([], 50) is None
    rows = []
    for index, seconds in enumerate((2, 4, 6, 8, 10)):
        start = datetime(2026, 3, 2, 10, index, tzinfo=timezone.utc)
        rows.append(row(start.strftime("%Y-%m-%dT%H:%M:%SZ"), "PreToolUse", tool_name="read_file", tool_use_id=f"t{index}"))
        rows.append(row((start + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ"), "PostToolUse", tool_name="read_file", tool_use_id=f"t{index}"))
    rows.append(row("2026-03-02T10:30:00Z", "PreToolUse", tool_name="execute_command", tool_use_id="lost"))
    rows.append(row("2026-03-02T10:31:00Z", "PreToolUse", tool_name="execute_command", tool_use_id="blocked", decision="blocked"))
    perf = summaries.performance(rows, Scope())
    read = next(item for item in perf["tools"] if item["tool"] == "read_file")
    assert (read["p50_s"], read["p95_s"]) == (6.0, 9.6)
    assert perf["kpis"]["tool_failure_rate_pct"]["value"] == round(1 / 6 * 100, 1)
    turns = [row("2026-03-02T09:00:00Z"), row("2026-03-02T09:01:00Z"), row("2026-03-02T09:05:00Z", "Stop"),
             row("2026-03-02T09:10:00Z"), row("2026-03-02T09:12:00Z", "Stop")]
    assert summaries.performance(turns, Scope())["kpis"]["turn_p50_s"]["value"] == 210.0


def test_governance_check_time_is_stored_and_shown():
    response = hook("UserPromptSubmit", "perf-ivy", "PRF-101", prompt="hello")
    body = client.get(f"/api/v1/events/{response.json()['event_id']}", auth=AUTH).json()
    assert body["event"]["check_ms"] >= 0
    labels = {item["label"]: item["value"] for item in body["view"]["technical"]}
    assert labels["Governance check time"].endswith(" ms")


# ---------------------------------------------------------------- violations

def test_block_rate_and_repeat_blocks():
    rows = [
        row("2026-03-02T10:00:00Z"), row("2026-03-02T10:01:00Z", "PreToolUse"),
        row("2026-03-02T10:02:00Z", "PreToolUse", decision="blocked", rule_id="GOV-GIT-001", rule_name="Unsafe git command"),
        row("2026-03-02T10:03:00Z", "PreToolUse", decision="blocked", rule_id="GOV-GIT-001", rule_name="Unsafe git command"),
        row("2026-03-02T10:04:00Z", "PreToolUse", user="jo", decision="blocked", rule_id="GOV-PKG-001", rule_name="x"),
        row("2026-03-02T10:05:00Z", "Stop"),
    ]
    numbers = summaries.block_numbers(rows)
    assert numbers == {"blocks": 3, "block_rate": 60.0, "users_affected": 2, "repeat_blocks": 1}
    ranked = summaries.violations(rows, Scope())["block_rate_by_user"]
    assert ranked["items"] == [] and ranked["unranked"] == 2    # fewer than 20 actions each
    busy = rows + [row(f"2026-03-02T11:{minute:02d}:00Z", "PreToolUse") for minute in range(20)]
    ranked = summaries.violations(busy, Scope())["block_rate_by_user"]
    assert [(item["user"], item["block_rate"]) for item in ranked["items"]] == [("sam", round(2 / 24 * 100, 2))]
    assert ranked["unranked"] == 1


def test_top_n_with_other():
    items = [{"user": f"u{index:02d}", "blocked": index} for index in range(1, 15)]
    result = summaries.top_n(items, "blocked", "user")
    assert [item["user"] for item in result["items"][:3]] == ["u14", "u13", "u12"]
    assert len(result["items"]) == 11 and result["truncated"] and result["total"] == 14
    other = result["items"][-1]
    assert other["user"] == "Other (4)" and other["blocked"] == 1 + 2 + 3 + 4
    assert summaries.top_n(items[:3], "blocked", "user")["truncated"] is False
    tied = summaries.top_n([{"user": "b", "blocked": 1}, {"user": "a", "blocked": 1}], "blocked", "user")
    assert [item["user"] for item in tied["items"]] == ["a", "b"]


def test_bucket_selection():
    def view(days):
        return summaries.View([], Scope.parse("2026-01-01", (summaries.date(2026, 1, 1) + timedelta(days=days - 1)).isoformat(), None, 0))
    assert view(31).granularity() == "day"
    assert view(32).granularity() == "week" and view(183).granularity() == "week"
    assert view(184).granularity() == "month"
    weekly = view(60)
    assert weekly.bucket(summaries.date(2026, 1, 8)) == summaries.date(2026, 1, 5)   # Monday of the ISO week
    assert summaries.View([], Scope.parse("2026-01-01", "2026-12-31", None, 0)).buckets()[1] == summaries.date(2026, 2, 1)


# ---------------------------------------------------------------- delivery ROI

def test_hands_on_minutes_skips_long_gaps():
    times = ["2026-03-02T10:00:00Z", "2026-03-02T10:10:00Z", "2026-03-02T10:25:00Z", "2026-03-02T11:00:00Z", "2026-03-02T11:05:00Z"]
    # 10 + 15 + (35 skipped) + 5
    assert summaries.hands_on_minutes(times) == 30.0
    assert summaries.hands_on_minutes([]) is None


def _ticket(ticket, start_hour, merged=True, cost=1.0):
    day = "2026-03-02"
    base = [
        lab_row(f"{day}T{start_hour:02d}:00:00Z", "ticket_started", ticket=ticket),
        row(f"{day}T{start_hour:02d}:01:00Z", ticket=ticket, session=ticket),
        row(f"{day}T{start_hour:02d}:11:00Z", "PreToolUse", ticket=ticket, session=ticket),
        row(f"{day}T{start_hour:02d}:31:00Z", "Stop", ticket=ticket, session=ticket, lab_cost=cost),
        lab_row(f"{day}T{start_hour:02d}:40:00Z", "pr_opened", ticket=ticket),
    ]
    if merged:
        base.append(lab_row(f"{day}T{start_hour + 1:02d}:00:00Z", "merged", ticket=ticket))
    return base


def test_delivery_tiles_hands_on_and_fully_loaded_cost():
    rows = _ticket("R-1", 8, cost=2.0) + _ticket("R-2", 10, cost=2.0) + _ticket("R-3", 12, cost=2.0) + _ticket("R-4", 14, merged=False, cost=6.0)
    result = summaries.delivery(rows, Scope())
    tickets = {item["ticket"]: item for item in result["tickets"]}
    # first prompt 01 -> 11 (10) -> 31 (20, over 15: 0) -> PR 40 (9) = 19 minutes
    assert tickets["R-1"]["hands_on_hours"] == round(19 / 60, 2)
    assert "estimate_hours" not in tickets["R-1"]
    roi = result["roi"]
    assert (roi["merged"], roi["opened"]) == (3, 4)
    assert roi["avg_minutes_to_pr"] == 40.0 and roi["avg_minutes_to_merge"] == 60.0
    assert roi["bobcoins_per_merged_pr"] == round(12.0 / 3, 4)          # fully loaded, includes unmerged R-4
    assert roi["usd_per_merged_pr"] == 2.0
    assert roi["bobcoins_per_merged_pr_direct"] == 2.0                  # merged tickets only
    assert roi["first_try_pass_rate_pct"] is None
    assert "estimated_saved_hours" not in roi


def test_ticket_estimate_is_not_a_lab_event():
    body = {"kind": "ticket_estimate", "user": "jira", "ticket": "EST-1", "data": {"hours": 4.5}}
    assert client.post("/api/v1/lab/events", headers={"Authorization": f"Bearer {TOKEN}"}, json=body).status_code == 422


# ---------------------------------------------------------------- drawer, export, stream

def test_drawer_sentence_and_empty_fields():
    event = {"user_name": "sam", "decision": "blocked", "hook_event": "PreToolUse", "tool_name": "execute_command",
             "rule_id": "GOV-GIT-001", "lab_ticket": "KAN-205", "occurred_at": "2026-10-12T16:43:00Z",
             "tool_input_content": json.dumps({"command": "git commit --no-verify -m 'x'"})}
    assert detail.sentence(event, 240) == "Sam tried to run a git command that skips the safety checks on KAN-205 at Oct 12, 12:43 PM."
    prompt = {"user_name": "ana", "decision": "allowed", "hook_event": "UserPromptSubmit", "occurred_at": "2026-10-12T16:43:00Z"}
    assert detail.sentence(prompt) == "Ana sent a prompt at Oct 12, 4:43 PM."
    write = {"user_name": "jo", "decision": "blocked", "hook_event": "PreToolUse", "tool_name": "write_file",
             "tool_input_content": json.dumps({"path": "app.py", "content": "x"})}
    assert detail.sentence(write) == "Jo tried to write to app.py."
    assert detail.title({"hook_event": "Stop"}) == "Session ended"
    view = detail.build({**prompt, "workspace": "no-folder"}, None)
    assert "why" not in view and "remediation" not in view
    assert all(item["value"] not in (None, "", "no-folder") for item in view["context"] + view["technical"])

    response = hook("UserPromptSubmit", "drawer-lee", "DRW-1", prompt="hello there")
    body = client.get(f"/api/v1/events/{response.json()['event_id']}", auth=AUTH).json()
    assert all(value not in (None, "", [], {}) for value in body["event"].values())
    assert "rule_id" not in body["event"] and "tool_duration_ms" not in body["event"]
    assert body["view"]["title"] == "Prompt sent" and body["view"]["status"] == "Allowed"


def test_blocked_event_drawer_has_why_and_what_to_do():
    response = hook("PreToolUse", "drawer-kai", "DRW-2", tool_name="execute_command", tool_use_id="d2",
                    tool_input={"command": "git push --force origin main"})
    view = client.get(f"/api/v1/events/{response.json()['event_id']}", auth=AUTH).json()["view"]
    assert view["title"] == "Unsafe git command" and view["status"] == "Blocked"
    assert view["remediation"].startswith("Push your ticket branch")
    assert view["rule_id"] == "GOV-GIT-001" and view["attempted"] == "git push --force origin main"


def test_jsonl_export_is_redacted_and_has_team():
    secret = "ghp_abcdefghijklmnopqrstuvwxyz1234567890"
    hook("UserPromptSubmit", "jsonl-max", "JSL-1", headers={"X-Governance-Team": "Platform"}, prompt=f"token {secret}")
    response = client.get("/api/v1/events.jsonl?user=jsonl-max", auth=AUTH)
    assert response.status_code == 200 and secret not in response.text
    records = [json.loads(line) for line in response.text.splitlines()]
    assert records and records[0]["team"] == "Platform" and "prompt_content" not in records[0]
    assert client.get("/api/v1/events.jsonl").status_code == 401
    assert client.get("/api/v1/events?user=jsonl-max&team=Platform", auth=AUTH).json()["count"] == 1
    assert client.get("/api/v1/events?user=jsonl-max&team=Field%20Apps", auth=AUTH).json()["count"] == 0


def test_stream_emits_ingested_events():
    response = hook("UserPromptSubmit", "stream-zoe", "STR-1", prompt="hi")
    event_id = response.json()["event_id"]
    stream = client.get("/api/v1/stream?once=1", auth=AUTH)
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert stream.headers["x-accel-buffering"] == "no"
    assert "no-cache" in stream.headers["cache-control"]
    assert event_id in stream.text and '"user": "stream-zoe"' in stream.text
    assert client.get("/api/v1/stream?once=1").status_code == 401


def test_spend_equation_reconciles_with_overview():
    rows = [
        row("2026-03-02T10:00:00Z", session="a"), row("2026-03-02T10:05:00Z", "Stop", session="a", lab_cost=2.5, lab_turns=3),
        row("2026-03-02T11:00:00Z", user="jo", session="b"), row("2026-03-02T11:05:00Z", "Stop", user="jo", session="b", lab_cost=1.25, lab_turns=2),
        {**row("2026-03-02T12:00:00Z", "Stop", user="ci-reviewer", session="ci", lab_cost=0.75, lab_turns=1), "lab_role": "ci-reviewer"},
    ]
    scope = Scope.parse("2026-03-01", "2026-03-07", None, 0)
    eq = {key: item["value"] for key, item in summaries.cost(rows, scope)["equation"].items()}
    product = eq["active_people"] * eq["sessions_per_person"] * eq["turns_per_session"] * eq["bobcoins_per_turn"]
    assert abs(product - eq["people_bobcoins"]) < 1e-6
    assert eq["people_bobcoins"] + eq["ci_bobcoins"] == eq["total_bobcoins"]
    assert eq["total_bobcoins"] == summaries.overview(rows, scope)["kpis"]["bobcoins"]["value"] == 4.5


def test_budget_used_is_month_to_date_whatever_the_range(monkeypatch):
    monkeypatch.setenv("LAB_BUDGETS", json.dumps({"teams": {"Platform": 100, "Field Apps": 100}, "default_person": 50}))
    monkeypatch.setattr(summaries.Scope, "today", lambda self: summaries.date(2026, 3, 20))
    rows = [
        row("2026-03-03T10:00:00Z", "Stop", session="early", lab_cost=40.0),   # this month, outside the 7-day range
        row("2026-03-18T10:00:00Z", "Stop", session="late", lab_cost=24.1),    # inside the range
        row("2026-02-25T10:00:00Z", "Stop", session="feb", lab_cost=90.0),     # last month
    ]
    overview = summaries.overview(rows, Scope.parse("2026-03-14", "2026-03-20", None, 0))
    assert overview["kpis"]["bobcoins"]["value"] == 24.1
    assert overview["kpis"]["budget_used_bobcoins"]["value"] == 64.1
    assert overview["kpis"]["budget_total"]["value"] == 200
    assert overview["kpis"]["budget_used_pct"]["value"] == 32.0
    # A past range does not move the month: still the current month to date.
    past = summaries.overview(rows, Scope.parse("2026-02-20", "2026-02-26", None, 0))
    assert past["kpis"]["budget_used_pct"]["value"] == 32.0


def test_user_and_team_budget_fields_are_filled(monkeypatch):
    monkeypatch.setenv("LAB_BUDGETS", json.dumps({"teams": {"Platform": 100}, "default_person": 50, "people": {"sam": 20}}))
    monkeypatch.setattr(summaries.Scope, "today", lambda self: summaries.date(2026, 3, 7))
    rows = [
        row("2026-03-02T10:00:00Z", "Stop", user="priya", session="p", lab_cost=41.82),
        row("2026-03-03T10:00:00Z", "Stop", user="sam", session="s", lab_cost=3.3),
        {**row("2026-03-03T11:00:00Z", "Stop", user="ci-reviewer", team=None, session="ci", lab_cost=1.0), "lab_role": "ci-reviewer"},
    ]
    scope = Scope.parse("2026-03-06", "2026-03-07", None, 0)   # range excludes the spend: budgets are month to date
    cost = summaries.cost(rows, scope)
    people = {item["user"]: item for item in cost["people"]}
    assert people == {} or all(item["budget"] for item in people.values())
    budget_people = {item["name"]: item for item in cost["budgets"]["people"]}
    assert (budget_people["priya"]["bobcoins"], budget_people["priya"]["budget"], budget_people["priya"]["pct"]) == (41.82, 50.0, 83.6)
    assert (budget_people["sam"]["budget"], budget_people["sam"]["pct"]) == (20.0, 16.5)
    wide = summaries.cost(rows, Scope.parse("2026-03-01", "2026-03-07", None, 0))
    for item in wide["people"]:
        assert item["budget"] is not None and item["budget_bobcoins"] is not None and item["budget_pct"] is not None
    team = next(item for item in summaries.overview(rows, scope)["by_team"] if item["team"] == "Platform")
    assert (team["budget"], team["budget_bobcoins"], team["budget_used_pct"]) == (100.0, 46.12, 46.1)


def test_content_is_masked_at_ingest_before_storage():
    fake = "Zx9QwErTy7UiOp3AsDfGh5JkLm2Nq8"
    response = hook("UserPromptSubmit", "mask-ida", "MSK-1", prompt=f"call 415-555-0142 and use {fake} please")
    stored = db._events[response.json()["event_id"]]
    raw = json.dumps(stored)
    assert fake not in raw and "415-555-0142" not in raw
    assert f"[masked {len(fake)} chars]" in stored["prompt_content"] and "[masked 12 chars]" in stored["prompt_content"]
    on_disk = "".join(path.read_text() for path in __import__("pathlib").Path(os.environ["DATA_DIR"]).rglob("*.json"))
    assert fake not in on_disk
    # Phone numbers written to files under tests/ are fixture data and stay.
    kept = hook("PreToolUse", "mask-ida", "MSK-1", tool_name="write_file", tool_use_id="m1",
                tool_input={"path": "tests/test_phone.py", "content": "PHONE = '415-555-0142'"})
    assert "415-555-0142" in db._events[kept.json()["event_id"]]["tool_input_content"]


def test_session_filter_and_per_turn_bobcoins():
    rows = [
        row("2026-03-02T10:00:00Z", session="sx"), row("2026-03-02T10:02:00Z", "Stop", session="sx", lab_cost=1.0, lab_turns=1),
        row("2026-03-02T10:05:00Z", session="sx"), row("2026-03-02T10:09:00Z", "Stop", session="sx", lab_cost=3.5, lab_turns=2),
        row("2026-03-02T10:12:00Z", "Stop", session="sx", lab_cost=3.5, lab_turns=2),
        row("2026-03-02T11:00:00Z", "Stop", session="other", lab_cost=9.0),
    ]
    assert [turn["bobcoins"] for turn in summaries.per_turn([item for item in rows if item["session_id"] == "sx"])] == [1.0, 2.5, 0.0]
    result = summaries.session_summary(rows, "sx")
    assert (result["bobcoins"], result["turns"], result["events"], result["duration_minutes"]) == (3.5, 2, 5, 12.0)
    assert summaries.session_summary(rows, "missing") is None
    response = hook("UserPromptSubmit", "sess-ola", "SES-1", session="raw-session-1", prompt="hi")
    session_id = client.get(f"/api/v1/events/{response.json()['event_id']}", auth=AUTH).json()["event"]["session_id"]
    hook("UserPromptSubmit", "sess-ola", "SES-1", session="raw-session-2", prompt="other")
    listed = client.get(f"/api/v1/events?session={session_id}", auth=AUTH).json()
    assert listed["count"] == 1
    assert client.get(f"/api/v1/sessions/{session_id}", auth=AUTH).json()["user"] == "sess-ola"
    assert client.get("/api/v1/sessions/nope", auth=AUTH).status_code == 404


def test_ci_review_details_and_links():
    body = {"kind": "ci_result", "user": "ci-reviewer", "ticket": "CIR-1", "pr": 4,
            "data": {"verdict": "FAIL", "findings": 2, "criteria_met": 5, "criteria_total": 7, "tests_passed": 9, "tests_total": 10,
                     "findings_list": ["Missing test for the empty list", "Hard-coded phone 415-555-0100"],
                     "pr_url": "https://github.com/example/repo/pull/4", "run_url": "https://github.com/example/repo/actions/runs/1"}}
    event_id = client.post("/api/v1/lab/events", headers={"Authorization": f"Bearer {TOKEN}"}, json=body).json()["event_id"]
    view = client.get(f"/api/v1/events/{event_id}", auth=AUTH).json()["view"]
    details = view["details"]
    assert (details["verdict"], details["criteria"], details["tests"]) == ("FAIL", "5 of 7", "9 of 10")
    assert details["findings_list"][0] == "Missing test for the empty list" and "0100" not in details["findings_list"][1]
    assert details["pr_url"].endswith("/pull/4") and details["run_url"].endswith("/runs/1")
    body["data"]["pr_url"] = "javascript:alert(1)"
    assert client.post("/api/v1/lab/events", headers={"Authorization": f"Bearer {TOKEN}"}, json=body).status_code == 422
