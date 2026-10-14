import csv
import io
import json
import math
import os
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="bob-governance-metrics-test-"))
os.environ.setdefault("INGEST_TOKEN", "test-ingest-token")
os.environ.setdefault("DASHBOARD_USER", "governance")
os.environ.setdefault("DASHBOARD_PASSWORD", "test-dashboard-password")

from fastapi.testclient import TestClient

from app import db, metrics, summaries
from app.summaries import Scope
from app.main import app, redact
from app.policies import POLICY_VERSION, RULES, default_policy_config

TOKEN = os.environ["INGEST_TOKEN"]
AUTH = (os.environ["DASHBOARD_USER"], os.environ["DASHBOARD_PASSWORD"])
client = TestClient(app)
db.init_db()
db.ensure_policy(default_policy_config(), POLICY_VERSION)


def headers(user, ticket, **extra):
    return {
        "Authorization": f"Bearer {TOKEN}", "X-Governance-User": user,
        "X-Governance-Device": f"{user}-laptop", "X-Lab-Ticket": ticket,
        "X-Lab-Role": "participant", **extra,
    }


def hook(event, user, ticket, session="s-1", extra_headers=None, **payload):
    body = {"hook_event_name": event, "session_id": session, "cwd": "/work/lab", **payload}
    return client.post("/api/v1/hooks", headers=headers(user, ticket, **(extra_headers or {})), json=body)


def stop(time, session, cost=None, tokens=None, turns=None, user="sam", ticket="T-1", day="2026-01-01"):
    return {
        "event_id": f"{session}-{time}", "source": "mdm-enforced-hook", "hook_event": "Stop",
        "decision": "allowed", "user_name": user, "lab_ticket": ticket, "session_id": session,
        "occurred_at": f"{day}T{time}:00Z", "lab_cost": cost, "lab_tokens": tokens, "lab_turns": turns,
    }


def walk_numbers(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_numbers(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_numbers(child)
    elif isinstance(value, float):
        yield value


def test_usage_takes_the_max_per_session_then_sums_per_user_ticket_and_day():
    rows = [
        stop("10:00", "a", cost=1.0, tokens=1000, turns=2),
        stop("10:30", "a", cost=2.5, tokens=4000, turns=5),
        stop("10:45", "a", cost=2.0, tokens=3500, turns=4),  # lower value later: no extra spend
        stop("11:00", "b", cost=1.5, tokens=2000, turns=3),
        stop("09:00", "c", cost=0.75, tokens=500, turns=1, user="priya", ticket="T-2", day="2026-01-02"),
    ]
    deltas = metrics.usage_deltas(rows)
    assert sum(record["bobcoins"] for record in deltas) == 4.75
    cost = summaries.cost(rows, Scope())
    sam = next(person for person in cost["people"] if person["user"] == "sam")
    assert sam["bobcoins"] == 4.0
    assert sam["tokens"] == 6000
    assert sam["turns"] == 8
    overview = summaries.overview(rows, Scope())
    assert overview["kpis"]["bobcoins"]["value"] == 4.75
    by_day = {item["day"]: item["bobcoins"] for item in overview["spend_by_team"]}
    assert by_day == {"2026-01-01": 4.0, "2026-01-02": 0.75}
    assert metrics.bobcoins_by_ticket(rows) == {"T-1": 4.0, "T-2": 0.75}
    assert sum(day["total"] for day in cost["daily"]) == 4.75


def test_non_stop_costs_count_as_sent():
    rows = [
        {"event_id": "p1", "source": "mdm-enforced-hook", "hook_event": "UserPromptSubmit", "session_id": "x",
         "user_name": "sam", "lab_ticket": "T-1", "occurred_at": "2026-01-01T10:00:00Z", "lab_cost": 0.5},
        {"event_id": "p2", "source": "mdm-enforced-hook", "hook_event": "UserPromptSubmit", "session_id": "x",
         "user_name": "sam", "lab_ticket": "T-1", "occurred_at": "2026-01-01T10:05:00Z", "lab_cost": 0.5},
    ]
    assert metrics.bobcoins_by_ticket(rows) == {"T-1": 1.0}


def test_stop_headers_are_stored_and_aggregated_through_the_hook(monkeypatch):
    monkeypatch.delenv("BOBCOIN_USD_RATE", raising=False)
    user, ticket = "usage-ana", "USE-301"
    hook("UserPromptSubmit", user, ticket, session="ana-1", prompt="Plan the ticket")
    first = hook("Stop", user, ticket, session="ana-1", last_assistant_message="Done",
                 extra_headers={"X-Lab-Cost": "1.2", "X-Lab-Tokens": "15000", "X-Lab-Turns": "3"})
    hook("Stop", user, ticket, session="ana-1", last_assistant_message="Done",
         extra_headers={"X-Lab-Cost": "3.87", "X-Lab-Tokens": "42000", "X-Lab-Turns": "7"})
    hook("Stop", user, ticket, session="ana-1", extra_headers={"X-Lab-Cost": "junk", "X-Lab-Tokens": "-4"})
    event = client.get(f"/api/v1/events/{first.json()['event_id']}", auth=AUTH).json()["event"]
    assert (event["lab_cost"], event["lab_tokens"], event["lab_turns"]) == (1.2, 15000, 3)
    cost = client.get("/api/v1/cost/summary", auth=AUTH).json()
    ana = next(person for person in cost["people"] if person["user"] == user)
    assert ana["bobcoins"] == 3.87
    assert ana["tokens"] == 42000
    assert ana["turns"] == 7
    assert ana["sessions"] == 1
    # Default rate: IBM enterprise packs, $500 per 1,000 Bobcoins.
    assert cost["usd_rate"] == 0.5
    assert "enterprise pack" in cost["usd_rate_basis"]
    assert ana["usd"] == 1.94
    tickets = client.get("/api/v1/delivery/summary", auth=AUTH).json()["tickets"]
    ticket_row = next(item for item in tickets if item["ticket"] == ticket)
    assert ticket_row["bobcoins"] == 3.87 and ticket_row["usd"] == 1.94


def test_usd_is_null_without_a_rate_and_follows_the_configured_rate(monkeypatch):
    rows = [stop("10:00", "a", cost=3.87)]
    monkeypatch.delenv("BOBCOIN_USD_RATE", raising=False)
    assert summaries.cost(rows, Scope())["people"][0]["usd"] == 1.94
    assert summaries.overview(rows, Scope())["kpis"]["usd"]["value"] == 1.94
    monkeypatch.setenv("BOBCOIN_USD_RATE", "off")
    cost = summaries.cost(rows, Scope())
    assert cost["usd_rate"] is None and cost["usd_rate_basis"] is None
    assert cost["people"][0]["usd"] is None
    assert summaries.overview(rows, Scope())["kpis"]["usd"]["value"] is None
    monkeypatch.setenv("BOBCOIN_USD_RATE", "0.55")
    cost = summaries.cost(rows, Scope())
    assert cost["usd_rate"] == 0.55
    assert cost["people"][0]["usd"] == 2.13
    assert cost["usd_rate_basis"] == "BOBCOIN_USD_RATE setting"


def test_empty_data_has_no_nan_and_null_metrics():
    scope = Scope.parse("2026-01-01", "2026-01-07", None, 0)
    for payload in (
        summaries.overview([], scope), summaries.cost([], scope), summaries.delivery([], scope),
        summaries.performance([], scope), summaries.violations([], scope), summaries.rules([], scope, RULES, {}),
    ):
        assert all(math.isfinite(value) for value in walk_numbers(payload))
        json.dumps(payload, allow_nan=False)
    overview = summaries.overview([], scope)
    assert overview["kpis"]["bobcoins"]["value"] is None
    assert overview["kpis"]["median_minutes_to_merge"]["value"] is None
    assert overview["kpis"]["bobcoins_per_merged_pr"]["value"] is None
    assert overview["kpis"]["bobcoins"]["delta_pct"] is None
    assert overview["spend_by_team"] == []
    assert summaries.cost([], scope)["outliers"] == []


def test_control_points_and_masked_excerpts():
    assert metrics.control_point({"hook_event": "UserPromptSubmit"}) == "Prompt submit"
    assert metrics.control_point({"hook_event": "PreToolUse", "tool_name": "write_file"}) == "File write"
    assert metrics.control_point({"hook_event": "PreToolUse", "tool_name": "execute_command",
                                  "tool_input_content": json.dumps({"command": "git status"})}) == "Git command"
    assert metrics.control_point({"hook_event": "PreToolUse", "tool_name": "execute_command",
                                  "tool_input_content": json.dumps({"command": "pip install x"})}) == "Tool call"
    row = {"hook_event": "UserPromptSubmit",
           "prompt_content": "Connect with password=Hunter2Hunter2 and key sk-abcdefghijklmnopqrstuvwxyz123456 " + "x" * 200}
    text = metrics.excerpt(row, redact)
    assert len(text) <= 80
    assert "Hunter2" not in text and "sk-abcdefghijklmnop" not in text
    phone = {"hook_event": "PreToolUse", "tool_name": "write_file",
             "tool_input_content": json.dumps({"path": "app.py", "content": "LINE = '415-555-0142'"})}
    assert metrics.excerpt(phone, redact) == "app.py: LINE = '415-555-****'"
    token = metrics.mask("value AbCdEf1234567890GhIjKlMnOp here")
    assert "AbCd****" in token and "567890" not in token


def test_violations_summary_breaks_down_blocks():
    user, ticket = "viol-kim", "VIO-401"
    secret = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
    hook("UserPromptSubmit", user, ticket, prompt=f"Use {secret} for the call")
    hook("PreToolUse", user, ticket, tool_name="execute_command", tool_use_id="v1",
         tool_input={"command": "pip install definitely-not-approved-pkg"})
    hook("PreToolUse", user, ticket, tool_name="write_file", tool_use_id="v2",
         tool_input={"path": "fieldops/app.py", "content": "PHONE = '415-555-0199'"})
    hook("PreToolUse", user, ticket, tool_name="execute_command", tool_use_id="v3",
         tool_input={"command": "git push --force origin main"})
    summary = client.get("/api/v1/violations/summary", auth=AUTH).json()
    mine = [row for row in summary["rows"] if row["user"] == user]
    assert {row["control_point"] for row in mine} == {"Prompt submit", "Tool call", "File write", "Git command"}
    assert all(row["decision"] == "blocked" and len(row["excerpt"]) <= 80 for row in mine)
    assert not any(secret in row["excerpt"] or "0199" in row["excerpt"] for row in mine)
    assert "by_control_point" not in summary
    assert any(item["user"] == user and item["violations"] == 4 for item in summary["by_user"]["items"])
    # 4 actions is below the 20-action minimum: not ranked, but counted.
    assert not any(item["user"] == user for item in summary["rate_by_user"]["items"])
    assert summary["rate_by_user"]["unranked"] >= 1
    rules = client.get("/api/v1/rules/summary", auth=AUTH).json()["rules"]
    assert [rule["rule_id"] for rule in rules] == list(RULES)
    git = next(rule for rule in rules if rule["rule_id"] == "GOV-GIT-001")
    assert git["blocked"] >= 1 and git["last_fired"] and git["control_point"] == "Git command"


def test_events_csv_is_protected_filtered_and_redacted():
    user, ticket = "csv-lee", "CSV-501"
    secret = "ghp_abcdefghijklmnopqrstuvwxyz1234567890"
    hook("UserPromptSubmit", user, ticket, prompt=f"token {secret}")
    hook("Stop", user, ticket, last_assistant_message="ok", extra_headers={"X-Lab-Cost": "3.87", "X-Lab-Tokens": "1200"})
    assert client.get("/api/v1/events.csv").status_code == 401
    response = client.get(f"/api/v1/events.csv?user={user}&ticket={ticket}", auth=AUTH)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert secret not in response.text
    table = list(csv.DictReader(io.StringIO(response.text)))
    assert len(table) == 2 and {row["user"] for row in table} == {user}
    assert "prompt_content" not in table[0] and "tool_input_content" not in table[0]
    assert {"bobcoins", "usd", "context_tokens", "control_point"} <= set(table[0])
    stopped = next(row for row in table if row["event_type"] == "Stop")
    assert (stopped["bobcoins"], stopped["usd"], stopped["context_tokens"]) == ("3.87", "1.94", "1200")
    blocked = next(row for row in table if row["decision"] == "blocked")
    assert blocked["control_point"] == "Prompt submit"
    assert client.get(f"/api/v1/events.csv?user={user}&decision=blocked", auth=AUTH).text.count("\n") == 2
    assert client.get(f"/api/v1/events.csv?user={user}&since=2999-01-01", auth=AUTH).text.count("\n") == 1
    assert metrics._csv_cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"


def test_events_date_range_filter():
    user = "range-max"
    hook("UserPromptSubmit", user, "RNG-601", prompt="hello")
    today = db.utcnow()[:10]
    listed = client.get(f"/api/v1/events?user={user}&since={today}&until={today}", auth=AUTH).json()
    assert listed["count"] == 1
    assert client.get(f"/api/v1/events?user={user}&until=2000-01-01", auth=AUTH).json()["count"] == 0


def test_ci_reviewer_is_automation_not_a_user():
    reviewer = {**stop("12:00", "ci", cost=2.0, tokens=900, turns=2, user="ci-reviewer"), "lab_role": "ci-reviewer"}
    rows = [stop("10:00", "a", cost=3.0, tokens=1000, turns=3), reviewer]
    cost = summaries.cost(rows, Scope())
    assert [person["user"] for person in cost["people"]] == ["sam"]
    assert cost["automation"]["label"] == "Automated review (CI)"
    assert cost["automation"]["bobcoins"] == 2.0
    assert metrics.bobcoins_by_ticket(rows) == {"T-1": 5.0}
    overview = summaries.overview(rows, Scope())
    assert overview["kpis"]["active_people"]["value"] == 1
    assert overview["kpis"]["bobcoins"]["value"] == 5.0


def test_days_follow_the_viewer_time_zone():
    rows = [stop("02:00", "a", cost=1.0, day="2026-01-02"), stop("10:00", "b", cost=1.0, day="2026-01-01")]
    utc = {item["day"] for item in summaries.overview(rows, Scope())["spend_by_team"]}
    assert utc == {"2026-01-01", "2026-01-02"}
    # UTC-5 (getTimezoneOffset 300): 02:00 UTC on Jan 2 is 21:00 on Jan 1.
    local = {item["day"] for item in summaries.overview(rows, Scope(tz_offset=300))["spend_by_team"]}
    assert local == {"2026-01-01"}
    assert client.get("/api/v1/overview/summary?tz_offset=300", auth=AUTH).status_code == 200
    assert client.get("/api/v1/violations/summary?tz_offset=9999", auth=AUTH).status_code == 422
    assert client.get("/api/v1/overview/summary?since=2026-02-02&until=2026-02-01", auth=AUTH).status_code == 422
    assert client.get("/api/v1/overview/summary").status_code == 401
