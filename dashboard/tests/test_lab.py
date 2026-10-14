import os
import tempfile
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="bob-governance-lab-test-"))
os.environ.setdefault("INGEST_TOKEN", "test-ingest-token")
os.environ.setdefault("DASHBOARD_USER", "governance")
os.environ.setdefault("DASHBOARD_PASSWORD", "test-dashboard-password")

from fastapi.testclient import TestClient

from app import db, lab
from app.main import app, git_findings, package_install_findings, pii_findings
from app.policies import DEFAULT_LAB_PACKAGE_ALLOWLIST, POLICY_VERSION, RULES, default_policy_config, lab_python_allowlist

TOKEN = os.environ["INGEST_TOKEN"]
AUTH = (os.environ["DASHBOARD_USER"], os.environ["DASHBOARD_PASSWORD"])
client = TestClient(app)
db.init_db()
db.ensure_policy(default_policy_config(), POLICY_VERSION)


def lab_headers(user="sam", ticket="LAB-901", role="participant", **extra):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "X-Governance-User": user,
        "X-Governance-Device": f"{user}-laptop",
        "X-Lab-Ticket": ticket,
        "X-Lab-Role": role,
        "X-Lab-Branch": f"feature/{ticket.lower()}",
    }
    headers.update(extra)
    return headers


def hook(event, headers=None, **payload):
    body = {"hook_event_name": event, "session_id": "lab-session", "cwd": "/work/bob-sdlc-lab", **payload}
    return client.post("/api/v1/hooks", headers=headers or lab_headers(), json=body)


def lab_event(kind, ticket="LAB-901", user="sam", pr=None, data=None, **extra):
    body = {"kind": kind, "user": user, "ticket": ticket, "pr": pr, "data": data or {}, **extra}
    return client.post("/api/v1/lab/events", headers={"Authorization": f"Bearer {TOKEN}"}, json=body)


def iso(minutes_from_now):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_lab_package_allowlist_defaults_and_env(monkeypatch):
    monkeypatch.delenv("LAB_PACKAGE_ALLOWLIST", raising=False)
    assert DEFAULT_LAB_PACKAGE_ALLOWLIST == "flask,pytest,mcp,pyyaml"
    assert lab_python_allowlist() == ["flask", "mcp", "pytest", "pyyaml"]
    allowlist = {"python": lab_python_allowlist(), "node": []}
    assert package_install_findings({"command": "pip install requests"}, allowlist) == ("python", ["requests"])
    assert package_install_findings({"command": "pip install flask pytest PyYAML"}, allowlist) == ("python", [])
    monkeypatch.setenv("LAB_PACKAGE_ALLOWLIST", " Requests , my_lib ,")
    assert lab_python_allowlist() == ["my-lib", "requests"]


def test_new_rules_are_in_the_catalog_and_default_policy():
    assert {"GOV-PII-001", "GOV-GIT-001"} <= set(RULES)
    ids = {entry["rule_id"] for entry in default_policy_config()["rules"]}
    assert {"GOV-PII-001", "GOV-GIT-001", "GOV-PKG-001"} <= ids


def test_pii_rule_matching():
    assert pii_findings("write_file", {"path": "fieldops/report.py", "content": "PHONE = '415-555-0142'"}) == ["415-555-0142"]
    assert pii_findings("apply_diff", {"path": "fieldops/report.py", "diff": "+ call 212-555-0199"}) == ["212-555-0199"]
    assert pii_findings("write_file", {"path": "fieldops/report.py", "content": "415-555-****"}) == []
    assert pii_findings("write_file", {"path": "data/customers.csv", "content": "415-555-0142"}) == []
    assert pii_findings("write_file", {"path": "/work/bob-sdlc-lab/tests/test_report.py", "content": "415-555-0142"}) == []
    assert pii_findings("read_file", {"path": "fieldops/report.py", "content": "415-555-0142"}) == []
    assert pii_findings("write_file", {"path": "fieldops/report.py", "content": "order 1415-555-01420"}) == []


def test_git_rule_matching():
    tool = "execute_command"
    assert git_findings(tool, {"command": "git commit -m wip --no-verify"})
    assert git_findings(tool, {"command": "git push --force origin feature/x"})
    assert git_findings(tool, {"command": "git push -f"})
    assert git_findings(tool, {"command": "git add . && git push origin main"})
    assert git_findings(tool, {"command": "git push origin HEAD:main"})
    assert git_findings(tool, {"command": "git push origin feature/kan-201"}) == []
    assert git_findings(tool, {"command": "git push --force-with-lease origin feature/x"}) == []
    assert git_findings(tool, {"command": "pip install --force flask"}) == []
    assert git_findings("write_file", {"command": "git push -f"}) == []


def test_pii_block_through_hook_and_exempt_paths():
    blocked = hook("PreToolUse", tool_name="write_file", tool_use_id="pii-1",
                   tool_input={"path": "fieldops/report.py", "content": "CONTACT = '415-555-0142'\n"})
    assert blocked.status_code == 200
    body = blocked.json()
    assert body["decision"] == "blocked"
    assert "GOV-PII-001" in body["reason"]
    assert "415-555-****" in body["reason"]
    allowed = hook("PreToolUse", tool_name="write_file", tool_use_id="pii-2",
                   tool_input={"path": "tests/test_report.py", "content": "assert x == '415-555-0142'"})
    assert allowed.json()["decision"] == "allowed"
    event = client.get(f"/api/v1/events/{body['event_id']}", auth=AUTH).json()["event"]
    assert event["rule_id"] == "GOV-PII-001"
    assert event["lab_path"] == "fieldops/report.py"


def test_git_block_through_hook():
    response = hook("PreToolUse", tool_name="execute_command", tool_use_id="git-1",
                    tool_input={"command": "git push --no-verify origin main"})
    body = response.json()
    assert body["decision"] == "blocked"
    assert "GOV-GIT-001" in body["reason"]
    assert "--no-verify" in body["reason"]


def test_package_rule_ignores_quotes_across_split_points_in_ordinary_commands(monkeypatch):
    monkeypatch.delenv("LAB_PACKAGE_ALLOWLIST", raising=False)
    allowlist = {"python": lab_python_allowlist(), "node": []}
    cases = [
        ("git add tests/x.py && git status --short", None),
        ("echo 'a|b'", None),
        (".venv/bin/pip install requests", "requests"),
        ("pip install 'requests>=2'", "requests"),
        ('pip install "unterminated', "unparseable-install-command"),
    ]
    for command, finding in cases:
        ecosystem, found = package_install_findings({"command": command}, allowlist)
        if finding is None:
            assert (ecosystem, found) == (None, []), command
        else:
            assert ecosystem == "python" and finding in found, command
    # Through the hook (allowlist-independent cases; the suite-wide allowlist may include requests).
    for index, (command, decision) in enumerate([
        ("git add tests/x.py && git status --short", "allowed"),
        ("echo 'a|b'", "allowed"),
        ('pip install "unterminated', "blocked"),
    ]):
        body = hook("PreToolUse", tool_name="execute_command", tool_use_id=f"pkg-split-{index}",
                    tool_input={"command": command}).json()
        assert body["decision"] == decision, command
        if decision == "blocked":
            assert "GOV-PKG-001" in body["reason"]


def test_lab_headers_are_stored_filtered_and_faceted():
    response = hook("UserPromptSubmit", headers=lab_headers(user="facet-user", ticket="lab-905", role="guide"),
                    prompt="Plan the ticket")
    event_id = response.json()["event_id"]
    event = client.get(f"/api/v1/events/{event_id}", auth=AUTH).json()["event"]
    assert event["lab_ticket"] == "LAB-905"
    assert event["lab_role"] == "guide"
    assert event["lab_branch"] == "feature/lab-905"
    listed = client.get("/api/v1/events?ticket=LAB-905&role=guide", auth=AUTH).json()["events"]
    assert [row["event_id"] for row in listed] == [event_id]
    assert listed[0]["lab_ticket"] == "LAB-905"
    facets = client.get("/api/v1/facets", auth=AUTH).json()
    assert "LAB-905" in facets["tickets"]
    assert "guide" in facets["roles"]


def test_invalid_lab_headers_are_dropped():
    response = hook("UserPromptSubmit", headers=lab_headers(ticket="not a ticket", role="admin"), prompt="hello")
    event = client.get(f"/api/v1/events/{response.json()['event_id']}", auth=AUTH).json()["event"]
    assert event["lab_ticket"] is None
    assert event["lab_role"] is None


def test_lab_events_require_ingest_token_and_valid_shape():
    body = {"kind": "pr_opened", "user": "sam", "ticket": "LAB-901", "pr": 7, "data": {}}
    assert client.post("/api/v1/lab/events", json=body).status_code == 401
    assert client.post("/api/v1/lab/events", headers={"Authorization": "Bearer wrong"}, json=body).status_code == 403
    assert lab_event("deployed").status_code == 422
    assert lab_event("pr_opened", ticket="nope").status_code == 422
    assert lab_event("ci_result", data={"verdict": "MAYBE"}).status_code == 422
    assert lab_event("ci_result", data={"verdict": "PASS", "findings": "many"}).status_code == 422
    assert lab_event("approved", data={"token": "x"}).status_code == 422
    assert client.get("/api/v1/lab/board").status_code == 401
    assert client.get("/api/v1/lab/roi").status_code == 401


def test_board_and_roi_follow_the_ticket_lifecycle():
    ticket = "LAB-910"
    headers = lab_headers(user="priya", ticket=ticket, **{"X-Lab-Cost": "0.5"})

    def row():
        rows = client.get("/api/v1/lab/board", auth=AUTH).json()["tickets"]
        return next(item for item in rows if item["ticket"] == ticket)

    hook("UserPromptSubmit", headers=headers, prompt="Read the ticket and plan")
    assert row()["status"] == "planning"
    hook("PreToolUse", headers=headers, tool_name="write_file", tool_use_id="b-1",
         tool_input={"path": "plans/LAB-910.md", "content": "plan"})
    assert row()["status"] == "planning"
    hook("PreToolUse", headers=headers, tool_name="write_file", tool_use_id="b-2",
         tool_input={"path": "fieldops/app.py", "content": "print('ok')"})
    assert row()["status"] == "building"
    hook("PreToolUse", headers=headers, tool_name="execute_command", tool_use_id="b-3",
         tool_input={"command": "pip install definitely-not-approved"})
    reviewer = lab_headers(user="ci-bot", ticket=ticket, role="ci-reviewer")
    hook("UserPromptSubmit", headers=reviewer, prompt="Review the diff")
    assert lab_event("pr_opened", ticket=ticket, user="priya", pr=12).status_code == 200
    assert row()["status"] == "pr_open"
    lab_event("ci_result", ticket=ticket, user="ci-bot", pr=12,
              data={"tests_passed": 9, "tests_total": 10, "verdict": "FAIL", "findings": 3, "blocking": 1, "seconds": 41.5})
    lab_event("ci_result", ticket=ticket, user="ci-bot", pr=12,
              data={"tests_passed": 10, "tests_total": 10, "verdict": "PASS", "findings": 1, "blocking": 0, "seconds": 38})
    lab_event("approved", ticket=ticket, user="guide", pr=12)
    merged = lab_event("merged", ticket=ticket, user="guide", pr=12, occurred_at=iso(60),
                       data={"approver": "guide", "review_rounds": 2, "lines_changed": 84})
    assert merged.status_code == 200

    final = row()
    assert final["status"] == "merged"
    assert final["user"] == "priya"
    assert final["prompts"] == 1
    assert final["tool_calls"] == 3
    assert final["blocks"] == 1
    assert final["ci"] == {"first_try_pass": False, "verdict": "PASS", "findings": 1, "runs": 2}
    assert final["pr"] == 12
    assert final["approver"] == "guide"
    assert final["review_rounds"] == 2
    assert final["cost_credits"] == 2.0
    assert 59 <= final["minutes"] <= 61

    roi = client.get("/api/v1/lab/roi?baseline_minutes=240", auth=AUTH).json()
    entry = next(item for item in roi["tickets"] if item["ticket"] == ticket)
    assert entry["blocks_before_merge"] == 1
    assert 179 <= entry["minutes_saved"] <= 181
    assert roi["totals"]["tickets_merged"] >= 1
    assert roi["review"]["prs_with_ci"] >= 1
    assert "merged" in roi["headline"]
    assert client.get("/api/v1/lab/roi?baseline_minutes=0", auth=AUTH).status_code == 422
    listed = client.get(f"/api/v1/events?ticket={ticket}&source=lab", auth=AUTH).json()["events"]
    assert {item["lab_kind"] for item in listed} == {"pr_opened", "ci_result", "approved", "merged"}


def test_roi_math_on_fixed_rows():
    def event(kind, minute, **extra):
        return {"source": "lab", "lab_kind": kind, "lab_ticket": "T-1",
                "occurred_at": f"2026-01-01T10:{minute:02d}:00Z", "user_name": "sam", **extra}

    rows = [
        {"source": "mdm-enforced-hook", "lab_ticket": "T-1", "lab_role": "participant", "user_name": "sam",
         "hook_event": "UserPromptSubmit", "decision": "allowed", "occurred_at": "2026-01-01T10:00:00Z", "lab_cost": 1.5},
        {"source": "mdm-enforced-hook", "lab_ticket": "T-1", "lab_role": "participant", "user_name": "sam",
         "hook_event": "PreToolUse", "decision": "blocked", "occurred_at": "2026-01-01T10:10:00Z", "lab_cost": 0.5},
        event("ci_result", 20, lab_data={"verdict": "PASS", "findings": 2}),
        event("merged", 40, lab_data={}),
    ]
    roi = lab.lab_roi(rows, baseline_minutes=100)
    assert roi["totals"]["merged_minutes"] == 40
    assert roi["totals"]["minutes_saved"] == 60
    assert roi["totals"]["pct_faster"] == 60
    assert roi["totals"]["cost_per_merged_pr"] == 2.0
    assert roi["totals"]["blocks_before_merge"] == 1
    assert roi["review"] == {"prs_with_ci": 1, "first_try_passes": 1, "first_try_pass_rate_pct": 100.0, "findings_per_pr": 2.0}
    rows_without_cost = [{key: value for key, value in row.items() if key != "lab_cost"} for row in rows]
    assert lab.lab_roi(rows_without_cost)["totals"]["cost_per_merged_pr"] is None


def test_lab_mode_publish_activates_policy_without_mdm(monkeypatch):
    monkeypatch.delenv("SIMPLEMDM_API_KEY", raising=False)
    monkeypatch.setenv("LAB_MODE", "1")
    draft = client.get("/api/v1/policy/draft", auth=AUTH).json()
    assert client.post("/api/v1/policy/publish", json={"expected_revision": draft["revision"]}).status_code == 401
    before = client.get("/api/v1/policies", auth=AUTH).json()["policy_version"]
    response = client.post("/api/v1/policy/publish", auth=AUTH, json={"expected_revision": draft["revision"]})
    assert response.status_code == 200, response.text
    assert response.json()["mode"] == "lab"
    after = client.get("/api/v1/policies", auth=AUTH).json()["policy_version"]
    assert after != before
    assert db._repo().get_json("policies/active.json")["version"] == after


def test_package_rule_ignores_shell_redirection(monkeypatch):
    monkeypatch.delenv("LAB_PACKAGE_ALLOWLIST", raising=False)
    from app.main import package_install_findings
    allow = {"python": ["flask", "pytest", "mcp", "pyyaml"], "node": []}
    assert package_install_findings({"command": ".venv/bin/pip install mcp==2.3.0 2>&1 | tail -3"}, allow)[1] == []
    assert package_install_findings({"command": "pip install mcp > /tmp/x.log 2>/dev/null"}, allow)[1] == []
    assert package_install_findings({"command": "pip install requests 2>&1"}, allow)[1] == ["requests"]
