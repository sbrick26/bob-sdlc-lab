import os
import json
import plistlib
import subprocess
import tempfile
import uuid
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="bob-governance-test-")
os.environ["INGEST_TOKEN"] = "test-ingest-token"
os.environ["DASHBOARD_USER"] = "governance"
os.environ["DASHBOARD_PASSWORD"] = "test-dashboard-password"
# The original suite exercises the broader product allowlist; the lab default is tested in test_lab.py.
os.environ.setdefault("LAB_PACKAGE_ALLOWLIST", "fastapi,httpx,numpy,pandas,pydantic,pytest,requests")

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.policies import POLICY_VERSION, default_policy_config

HEADERS = {
    "Authorization": "Bearer test-ingest-token",
    "X-Governance-User": "labtestvm",
    "X-Governance-Device": "Lab-Virtual-Machine",
    "X-Governance-Profile": "Bob Governance",
    "X-Governance-Profile-ID": "100001",
    "X-Governance-Policy-Version": "1.0.0",
    "X-Bob-Version": "2.1.0",
    "X-Bob-Channel": "insiders",
}
DASHBOARD_AUTH = ("governance", "test-dashboard-password")


def hook(event, **extra):
    payload = {
        "hook_event_name": event,
        "session_id": "session-1",
        "cwd": "/Users/demo/bob-hook-test",
        **extra,
    }
    return client.post("/api/v1/hooks", headers=HEADERS, json=payload)


client = TestClient(app)
db.init_db()
db.ensure_policy(default_policy_config(), POLICY_VERSION)


def test_dashboard_and_health():
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/").status_code == 401
    page = client.get("/", auth=DASHBOARD_AUTH).text
    assert "Governance" in page
    assert "Meridian" not in page


def test_clean_prompt_is_retained():
    response = hook("UserPromptSubmit", prompt="Explain this function and suggest tests")
    assert response.status_code == 200
    assert response.json()["decision"] == "allowed"
    listed = client.get("/api/v1/events?event=UserPromptSubmit", auth=DASHBOARD_AUTH).json()["events"]
    assert all("prompt_content" not in event for event in listed)
    event = client.get(
        f"/api/v1/events/{response.json()['event_id']}", auth=DASHBOARD_AUTH
    ).json()["event"]
    assert event["prompt_content"] == "Explain this function and suggest tests"
    assert event["content_logged"] == 1
    assert event["profile_id"] == "100001"


def test_secret_prompt_is_blocked_and_redacted():
    secret = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
    response = hook("UserPromptSubmit", prompt=f"Use this key {secret} to call the API")
    assert response.status_code == 200
    assert response.json()["decision"] == "blocked"
    event = client.get(
        f"/api/v1/events/{response.json()['event_id']}", auth=DASHBOARD_AUTH
    ).json()["event"]
    assert event["rule_id"] == "GOV-PROMPT-001"
    assert secret not in event["prompt_content"]
    assert "[REDACTED: sk-prefixed API key]" in event["prompt_content"]


def test_tool_duration_and_post_tool_context():
    pre = hook("PreToolUse", tool_name="shell", tool_use_id="tool-1", tool_input={"command": "pwd"})
    assert pre.json()["decision"] == "allowed"
    post = hook("PostToolUse", tool_name="shell", tool_use_id="tool-1", tool_input={"command": "pwd"}, tool_response="/tmp")
    assert post.json()["decision"] == "allowed"
    event = client.get("/api/v1/events?event=PostToolUse", auth=DASHBOARD_AUTH).json()["events"][0]
    assert event["tool_duration_ms"] is not None


def test_raw_normalized_event_fields_are_rejected():
    response = client.post(
        "/api/v1/events",
        headers={"Authorization": "Bearer test-ingest-token"},
        json={"prompt": "should not be accepted on normalized endpoint"},
    )
    assert response.status_code == 422
    response = client.post(
        "/api/v1/events",
        headers={"Authorization": "Bearer test-ingest-token"},
        json={"prompt_content": "should also be rejected"},
    )
    assert response.status_code == 422


def test_normalized_event_metadata_is_redacted_and_not_cacheable():
    secret = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "occurred_at": db.utcnow(),
        "user_name": "redaction-user",
        "device_name": "redaction-device",
        "source": "integration",
        "profile_name": "Bob Governance",
        "policy_version": "1.1.0",
        "hook_event": "PostToolUse",
        "decision": "observed",
        "severity": "high",
        "detail": f"Validator found {secret}",
        "evidence": f"token={secret}",
    }
    ingested = client.post(
        "/api/v1/events",
        headers={"Authorization": "Bearer test-ingest-token"},
        json=event,
    )
    assert ingested.status_code == 200
    response = client.get("/api/v1/events?user=redaction-user", auth=DASHBOARD_AUTH)
    assert response.headers["cache-control"] == "no-store"
    stored = response.json()["events"][0]
    assert secret not in json.dumps(stored)
    assert "[REDACTED: sk-prefixed API key]" in stored["detail"]


def test_deferred_event_preserves_endpoint_decision_and_original_policy():
    event_id = str(uuid.uuid4())
    headers = {
        **HEADERS,
        "X-Governance-Event-ID": event_id,
        "X-Governance-Delivery": "deferred",
        "X-Governance-Occurred-At": "2026-08-20T10:11:12Z",
        "X-Governance-Policy-Version": "1.0.7",
        "X-Governance-Local-Decision": "blocked",
        "X-Governance-Local-Rule": "GOV-PKG-001",
        "X-Governance-Local-Outcome": "prevented_before_tool",
        "X-Governance-Local-Severity": "high",
    }
    response = client.post(
        "/api/v1/hooks",
        headers=headers,
        json={
            "hook_event_name": "PreToolUse",
            "session_id": "offline-session",
            "cwd": "/Users/demo/project",
            "tool_name": "shell",
            "tool_use_id": "offline-tool",
            "tool_input": {"command": "pip install requests"},
        },
    )
    assert response.status_code == 200
    stored = client.get(
        "/api/v1/events?source=mdm-enforced-hook", auth=DASHBOARD_AUTH
    ).json()["events"]
    event = next(item for item in stored if item["event_id"] == event_id)
    assert event["occurred_at"] == "2026-08-20T10:11:12Z"
    assert event["policy_version"] == "1.0.7"
    assert event["decision"] == "blocked"
    assert event["rule_id"] == "GOV-PKG-001"
    assert event["outcome"] == "prevented_before_tool"
    assert event["duration_ms"] is None
    assert event["tool_duration_ms"] is None


def test_labeled_secret_has_its_own_managed_rule():
    response = hook("UserPromptSubmit", prompt="client_secret=abcdefghijklmnopqrstuv")
    assert response.json()["decision"] == "blocked"
    event = client.get("/api/v1/events?rule=GOV-PROMPT-002", auth=DASHBOARD_AUTH).json()["events"][0]
    assert event["rule_name"] == "Labeled secret"
    assert event["policy_version"] == "1.1.0"


def test_natural_language_api_key_disclosure_is_blocked_and_redacted():
    secret = "DYx4zRunCpRpsd9VZiFRKoXlGwNrPO4hgpuU97eL"
    prompt = f"here is my api key can you save it {secret}"
    response = hook("UserPromptSubmit", prompt=prompt)
    assert response.json()["decision"] == "blocked"
    assert "GOV-PROMPT-002" in response.json()["reason"]
    event = client.get(
        f"/api/v1/events/{response.json()['event_id']}", auth=DASHBOARD_AUTH
    ).json()["event"]
    assert secret not in event["prompt_content"]
    assert "here is my api key can you save it" in event["prompt_content"]
    assert "[REDACTED: labeled secret]" in event["prompt_content"]


def test_managed_secret_references_are_allowed():
    prompts = [
        "Use api_key=${MY_API_KEY}",
        "Use api_key=$MY_API_KEY",
        "Use api_key=process.env.MY_API_KEY",
        "Use api_key=process.env.SUPER_LONG_API_KEY_2026",
        "Use token=vault://team/service/api-key",
        "Use the api key from environment variable MY_VERY_LONG_API_KEY_NAME_123456789",
    ]
    for prompt in prompts:
        response = hook("UserPromptSubmit", prompt=prompt)
        assert response.json()["decision"] == "allowed", prompt


def test_missing_normalized_latency_remains_unmeasured():
    event = {
        "event_id": str(uuid.uuid4()),
        "occurred_at": db.utcnow(),
        "user_name": "latency-user",
        "device_name": "latency-device",
        "source": "test",
        "profile_name": "Latency Test",
        "policy_version": "1.1.0",
        "hook_event": "SessionStart",
        "decision": "allowed",
        "severity": "info",
    }
    response = client.post(
        "/api/v1/events",
        headers={"Authorization": "Bearer test-ingest-token"},
        json=event,
    )
    assert response.status_code == 200
    stored = client.get(
        "/api/v1/events?user=latency-user", auth=DASHBOARD_AUTH
    ).json()["events"][0]
    assert stored["duration_ms"] is None


def test_rule_catalog_is_protected_and_centralized():
    assert client.get("/api/v1/policies").status_code == 401
    catalog = client.get("/api/v1/policies", auth=DASHBOARD_AUTH).json()
    assert catalog["status"] == "active"
    assert {rule["rule_id"] for rule in catalog["rules"]} >= {"GOV-PROMPT-001", "GOV-TOOL-001", "GOV-PKG-001"}


def test_package_allowlist_blocks_only_unapproved_installs():
    allowed = [
        {"command": "python3 -m pip install requests==2.32.0"},
        {"command": "npm install react@19 react-dom@19"},
    ]
    for tool_input in allowed:
        response = hook("PreToolUse", tool_name="shell", tool_use_id=str(uuid.uuid4()), tool_input=tool_input)
        assert response.json()["decision"] == "allowed", tool_input

    blocked = [
        ({"command": "pip install suspicious-package"}, "suspicious-package"),
        ({"command": "npm i left-pad"}, "left-pad"),
        ({"command": "pip install -r requirements.txt"}, "dependency-manifest"),
        ({"command": "pip install --requirement=requirements.txt"}, "dependency-manifest"),
        ({"command": "pip install -rrequirements.txt"}, "dependency-manifest"),
        ({"command": "npm install"}, "dependency-manifest"),
        ({"command": "yarn install"}, "dependency-manifest"),
        ({"command": "pip install requests && pip install evil-package"}, "evil-package"),
        ({"command": "npm install react && npm install left-pad"}, "left-pad"),
    ]
    for tool_input, package in blocked:
        response = hook("PreToolUse", tool_name="shell", tool_use_id=str(uuid.uuid4()), tool_input=tool_input)
        assert response.json()["decision"] == "blocked"
        assert "GOV-PKG-001" in response.json()["reason"]
        assert package in response.json()["reason"]

    events = client.get("/api/v1/events?rule=GOV-PKG-001", auth=DASHBOARD_AUTH).json()["events"]
    assert len(events) >= 3
    assert all(event["outcome"] == "prevented_before_tool" for event in events)


def test_policy_draft_validate_save_publish_and_runtime_update():
    active_before = client.get("/api/v1/policies", auth=DASHBOARD_AUTH).json()["policy_version"]
    draft = client.get("/api/v1/policy/draft", auth=DASHBOARD_AUTH).json()
    assert draft["status"] == "draft"
    package_rule = next(rule for rule in draft["rules"] if rule["rule_id"] == "GOV-PKG-001")
    package_rule["configuration"]["allowlist"]["python"].append("approved-internal-lib")
    config = {
        "name": "Bob Governance",
        "rules": [
            {
                "rule_id": rule["rule_id"],
                "enabled": rule["enabled"],
                **({"configuration": rule["configuration"]} if rule.get("configuration") else {}),
            }
            for rule in draft["rules"]
        ],
        "offline": draft["offline"],
        "content": draft["content"],
    }

    validation = client.post(
        "/api/v1/policy/validate",
        auth=DASHBOARD_AUTH,
        json={"expected_revision": draft["revision"], "config": config},
    ).json()
    assert validation == {"valid": True, "errors": []}

    saved = client.put(
        "/api/v1/policy/draft",
        auth=DASHBOARD_AUTH,
        json={"expected_revision": draft["revision"], "config": config},
    )
    assert saved.status_code == 200
    saved_draft = saved.json()
    assert saved_draft["revision"] != draft["revision"]

    published = client.post(
        "/api/v1/policy/publish",
        auth=DASHBOARD_AUTH,
        json={"expected_revision": saved_draft["revision"]},
    )
    assert published.status_code == 503
    assert client.get("/api/v1/policies", auth=DASHBOARD_AUTH).json()["policy_version"] == active_before

    allowed = hook(
        "PreToolUse",
        tool_name="shell",
        tool_use_id=str(uuid.uuid4()),
        tool_input={"command": "pip install approved-internal-lib"},
    )
    assert allowed.json()["decision"] == "blocked"

    conflict = client.put(
        "/api/v1/policy/draft",
        auth=DASHBOARD_AUTH,
        json={"expected_revision": draft["revision"], "config": config},
    )
    assert conflict.status_code == 409


def test_compiled_managed_profile_contains_offline_queue_and_valid_shell():
    from app.profile import build_profile

    content = build_profile(
        config=default_policy_config(),
        version="9.9.9",
        api_url="https://governance.example.test",
        ingest_token="synthetic-test-token",
        profile_id="100001",
    )
    profile = plistlib.loads(content)
    encoded = profile["PayloadContent"][0]["PayloadContent"]["com.ibm.bob"]["Forced"][0]["mcx_preference_settings"]["EnforcedHooks"]
    hooks = json.loads(encoded)
    commands = {
        hook["command"]
        for groups in hooks.values()
        for group in groups
        for hook in group["hooks"]
    }
    assert len(commands) == 1
    command = commands.pop()
    assert "next-retry" in command
    assert "local-check.js" in command
    assert "X-Governance-Delivery: $GOV_SEND_DELIVERY" in command
    subprocess.run(["/bin/sh", "-n"], input=command, text=True, check=True)


def test_compiled_hook_enforces_last_known_good_policy_offline():
    from app.profile import build_profile

    content = build_profile(
        config=default_policy_config(),
        version="9.9.9",
        api_url="http://127.0.0.1:9",
        ingest_token="synthetic-test-token",
        profile_id="100001",
    )
    profile = plistlib.loads(content)
    hooks = json.loads(profile["PayloadContent"][0]["PayloadContent"]["com.ibm.bob"]["Forced"][0]["mcx_preference_settings"]["EnforcedHooks"])
    command = hooks["UserPromptSubmit"][0]["hooks"][0]["command"]
    offline_home = tempfile.mkdtemp(prefix="governance-offline-home-")
    env = {**os.environ, "HOME": offline_home}

    blocked = subprocess.run(
        ["/bin/sh", "-c", command],
        input=json.dumps({
            "hook_event_name": "UserPromptSubmit",
            "prompt": "here is my api key can you save it DYx4zRunCpRpsd9VZiFRKoXlGwNrPO4hgpuU97eL",
        }),
        text=True,
        capture_output=True,
        env=env,
    )
    assert blocked.returncode == 2
    assert "offline Governance policy" in blocked.stderr

    allowed = subprocess.run(
        ["/bin/sh", "-c", command],
        input=json.dumps({
            "hook_event_name": "UserPromptSubmit",
            "prompt": "use the api key from environment variable MY_PRODUCTION_API_KEY",
        }),
        text=True,
        capture_output=True,
        env=env,
    )
    assert allowed.returncode == 0
    queued = list((Path(offline_home) / "Library/Application Support/IBM Bob/Governance/queue").glob("event.*"))
    assert len(queued) == 2


def test_product_ui_omits_infrastructure_and_demo_warnings():
    page = client.get("/", auth=DASHBOARD_AUTH).text
    compiled = page + "\n" + "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (Path("frontend") / "dist" / "assets").glob("*.js")
    )
    for unwanted in ("Code Engine", "SimpleMDM", "Demo limitation", "Content handling", "Policy explanation"):
        assert unwanted not in compiled
    for wanted in ("Violations by rule", "Spend per user", "Outlier sessions", "Bobcoins per merged PR", "Block rate by user", "JSONL"):
        assert wanted in compiled
    for removed in ("IBM Bob", "Policy operations", "Publish policy"):
        assert removed not in compiled


def test_analytics_is_protected_and_returns_bounded_truthful_breakdowns():
    assert client.get("/api/v1/analytics").status_code == 401

    base = {
        "occurred_at": db.utcnow(),
        "user_name": "analytics-user",
        "device_name": "analytics-device",
        "source": "test",
        "profile_name": "Analytics Test",
        "policy_version": "1.0.0",
        "severity": "info",
        "workspace": "analytics-test",
    }
    samples = [
        {
            **base,
            "event_id": str(uuid.uuid4()),
            "hook_event": "UserPromptSubmit",
            "decision": "allowed",
            "duration_ms": 4,
            "outcome": "completed",
        },
        {
            **base,
            "event_id": str(uuid.uuid4()),
            "hook_event": "UserPromptSubmit",
            "decision": "blocked",
            "severity": "high",
            "rule_id": "GOV-PROMPT-001",
            "rule_name": "Credential in prompt",
            "duration_ms": 8,
            "outcome": "prevented_before_model",
        },
        {
            **base,
            "event_id": str(uuid.uuid4()),
            "hook_event": "PostToolUse",
            "decision": "observed",
            "severity": "high",
            "rule_id": "GOV-POST-001",
            "rule_name": "Credential in tool output",
            "tool_name": "shell",
            "tool_use_id": "analytics-tool-1",
            "duration_ms": 6,
            "tool_duration_ms": 125,
            "outcome": "finding_added_to_next_turn",
        },
    ]
    response = client.post(
        "/api/v1/events",
        headers={"Authorization": "Bearer test-ingest-token"},
        json=samples,
    )
    assert response.status_code == 200
    assert response.json()["inserted"] == 3

    response = client.get("/api/v1/analytics?days=30&granularity=day", auth=DASHBOARD_AUTH)
    assert response.status_code == 200
    analytics = response.json()
    assert analytics["window"]["granularity"] == "day"
    assert analytics["window"]["effective_days"] == 30
    assert len(analytics["top_users"]) <= 12
    assert len(analytics["rules"]) <= 20
    assert len(analytics["tools"]) <= 20

    user = next(item for item in analytics["top_users"] if item["user_name"] == "analytics-user")
    assert user["total"] == 3
    assert user["allowed"] == 1
    assert user["blocked"] == 1
    assert user["observed"] == 1
    assert user["enforceable_total"] == 2
    assert user["blocked_rate_pct"] == 50.0

    prompt_hooks = next(item for item in analytics["hook_events"] if item["hook_event"] == "UserPromptSubmit")
    assert prompt_hooks["total"] >= 2
    assert prompt_hooks["blocked"] >= 1
    prompt_rule = next(item for item in analytics["rules"] if item["rule_id"] == "GOV-PROMPT-001")
    assert prompt_rule["blocked"] >= 1
    shell = next(item for item in analytics["tools"] if item["tool_name"] == "shell")
    assert shell["avg_tool_duration_ms"] is not None
    assert shell["duration_samples"] >= 1

    overall = analytics["overall"]
    assert overall["total"] >= 3
    assert overall["reporting_users"] >= 1
    assert overall["policy_duration_samples"] >= 3
    assert overall["blocked_rate_pct"] == round(overall["blocked"] / overall["enforceable_total"] * 100, 1)


def test_hourly_analytics_window_is_capped_to_seven_days():
    analytics = client.get(
        "/api/v1/analytics?days=90&granularity=hour", auth=DASHBOARD_AUTH
    ).json()
    assert analytics["window"]["requested_days"] == 90
    assert analytics["window"]["effective_days"] == 7
    assert analytics["window"]["granularity"] == "hour"
