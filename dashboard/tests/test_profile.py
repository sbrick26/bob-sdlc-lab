import json
import os
import plistlib
import runpy
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.policies import default_policy_config
from app.profile import build_profile


def compiled_command(config, event="UserPromptSubmit"):
    content = build_profile(
        config=config,
        version="9.9.9",
        api_url="http://127.0.0.1:9",
        ingest_token="synthetic-test-token",
        profile_id="100001",
    )
    profile = plistlib.loads(content)
    encoded = profile["PayloadContent"][0]["PayloadContent"]["com.ibm.bob"]["Forced"][0]["mcx_preference_settings"]["EnforcedHooks"]
    return json.loads(encoded)[event][0]["hooks"][0]["command"]


def offline_home(tmp_path: Path) -> tuple[dict[str, str], Path]:
    root = tmp_path / "Library/Application Support/IBM Bob/Governance"
    root.mkdir(parents=True)
    (root / "next-retry").write_text(str(int(time.time()) + 3_600))
    return {**os.environ, "HOME": str(tmp_path)}, root


def run_hook(command: str, payload: dict, env: dict[str, str]):
    return subprocess.run(
        ["/bin/sh", "-c", command],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        timeout=30,
    )


def disable(config, *rule_ids):
    for entry in config["rules"]:
        if entry["rule_id"] in rule_ids:
            entry["enabled"] = False


def test_compiled_rule_states_and_custom_allowlist_are_enforced_offline(tmp_path):
    config = default_policy_config()
    disable(config, "GOV-PROMPT-001", "GOV-PROMPT-002", "GOV-TOOL-001")
    package = next(entry for entry in config["rules"] if entry["rule_id"] == "GOV-PKG-001")
    package["configuration"]["allowlist"] = {"python": ["internal_pkg"], "node": ["@team/sdk"]}
    prompt_command = compiled_command(config)
    tool_command = compiled_command(config, "PreToolUse")
    env, _ = offline_home(tmp_path)

    known = run_hook(prompt_command, {
        "hook_event_name": "UserPromptSubmit",
        "prompt": "Use sk-abcdefghijklmnopqrstuvwxyz1234567890",
    }, env)
    labeled = run_hook(prompt_command, {
        "hook_event_name": "UserPromptSubmit",
        "prompt": "api_key=abcdefghijklmnopqrstuv",
    }, env)
    tool_secret = run_hook(tool_command, {
        "hook_event_name": "PreToolUse",
        "tool_input": {"command": "curl -H 'token=abcdefghijklmnopqrstuv' example.test"},
    }, env)
    approved = run_hook(tool_command, {
        "hook_event_name": "PreToolUse",
        "tool_input": {"command": "pip install internal-pkg && npm install @team/sdk@2"},
    }, env)
    denied = run_hook(tool_command, {
        "hook_event_name": "PreToolUse",
        "tool_input": {"command": "pip install requests"},
    }, env)

    assert known.returncode == labeled.returncode == tool_secret.returncode == approved.returncode == 0
    assert denied.returncode == 2
    assert "GOV-PKG-001" in denied.stderr
    assert "requests" in denied.stderr


def test_disabled_package_rule_allows_unapproved_install_offline(tmp_path):
    config = default_policy_config()
    disable(config, "GOV-PKG-001")
    command = compiled_command(config, "PreToolUse")
    env, _ = offline_home(tmp_path)
    result = run_hook(command, {
        "hook_event_name": "PreToolUse",
        "tool_input": {"command": "pip install definitely-not-approved"},
    }, env)
    assert result.returncode == 0


@pytest.mark.parametrize("shell_command, expected", [
    ("pip install requests && npm install react && pip install evil-package", "evil-package"),
    ("python3 -m pip install -r requirements.txt", "dependency-manifest"),
    ("npm install", "dependency-manifest"),
    ("yarn install", "dependency-manifest"),
    ("pnpm add react | npm i left-pad", "left-pad"),
])
def test_offline_package_checker_covers_compound_and_manifest_installs(tmp_path, shell_command, expected):
    command = compiled_command(default_policy_config(), "PreToolUse")
    env, _ = offline_home(tmp_path)
    result = run_hook(command, {
        "hook_event_name": "PreToolUse",
        "tool_input": {"command": shell_command},
    }, env)
    assert result.returncode == 2
    assert "GOV-PKG-001" in result.stderr
    assert expected in result.stderr


def test_exact_secret_offline_metadata_is_structured_stable_and_private(tmp_path):
    command = compiled_command(default_policy_config())
    env, root = offline_home(tmp_path)
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "prompt": "here is my api key can you save it DYx4zRunCpRpsd9VZiFRKoXlGwNrPO4hgpuU97eL",
    }
    result = run_hook(command, payload, env)
    assert result.returncode == 2
    assert "GOV-PROMPT-002" in result.stderr

    event_dirs = sorted((root / "queue").glob("event.*"))
    assert len(event_dirs) == 1
    body = event_dirs[0] / "body.json"
    metadata = event_dirs[0] / "metadata.plist"
    assert json.loads(body.read_text()) == payload
    record = plistlib.loads(metadata.read_bytes())
    assert record["event_id"] in event_dirs[0].name
    assert record["occurred_at"].endswith("Z")
    assert record["policy_version"] == "9.9.9"
    assert record["local_decision"] == "blocked"
    assert record["local_rule"] == "GOV-PROMPT-002"
    assert record["local_outcome"] == "prevented_before_model"
    assert record["profile_id"] == "100001"
    assert stat.S_IMODE(event_dirs[0].stat().st_mode) == 0o700
    assert stat.S_IMODE(body.stat().st_mode) == 0o600
    assert stat.S_IMODE(metadata.stat().st_mode) == 0o600


def test_queue_bounds_fifo_and_dead_letter_counter_use_policy_values(tmp_path):
    config = default_policy_config()
    config["offline"].update({
        "queue_max_events": 2,
        "queue_max_bytes": 4_096,
        "retry_max_seconds": 7,
    })
    command = compiled_command(config)
    assert "-le 2" in command
    assert "-le 4096" in command
    assert "GOV_DELAY=7" in command
    env, root = offline_home(tmp_path)
    for marker in ("first", "second", "third"):
        result = run_hook(command, {
            "hook_event_name": "UserPromptSubmit",
            "prompt": marker,
        }, env)
        assert result.returncode == 0

    events = sorted((root / "queue").glob("event.*"))
    assert 0 < len(events) <= 2
    queued_prompts = [json.loads((event / "body.json").read_text())["prompt"] for event in events]
    assert "first" not in queued_prompts
    assert queued_prompts[-1] == "third"
    assert int((root / "dead-letter-count").read_text()) >= 1
    subprocess.run(["/bin/sh", "-n"], input=command, text=True, check=True)


def test_replay_command_preserves_managed_metadata_headers_and_short_timeout():
    command = compiled_command(default_policy_config())
    for header in (
        "X-Governance-Event-ID",
        "X-Governance-Occurred-At",
        "X-Governance-Policy-Version",
        "X-Governance-Local-Decision",
        "X-Governance-Local-Rule",
        "X-Governance-Local-Outcome",
        "X-Governance-User",
        "X-Governance-Device",
        "X-Governance-Profile-ID",
        "X-Bob-Version",
    ):
        assert header in command
    assert 'gov_send "$GOV_OLD" 1 deferred' in command
    assert "head -1" in command
    subprocess.run(["/bin/sh", "-n"], input=command, text=True, check=True)


def test_generator_writes_mobileconfig_with_private_mode(tmp_path, monkeypatch):
    output = tmp_path / "governance.mobileconfig"
    monkeypatch.setenv("USER", "profile-test")
    monkeypatch.setenv("GOVERNANCE_URL", "https://governance.example.test")
    monkeypatch.setattr(subprocess, "check_output", lambda *args, **kwargs: "synthetic-test-token\n")
    old_argv = sys.argv
    try:
        sys.argv = ["generate-governance-profile.py", str(output)]
        runpy.run_path(str(Path("scripts/generate-governance-profile.py")), run_name="__main__")
    finally:
        sys.argv = old_argv
    assert plistlib.loads(output.read_bytes())["PayloadIdentifier"] == "com.ibm.bob.governance"
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
