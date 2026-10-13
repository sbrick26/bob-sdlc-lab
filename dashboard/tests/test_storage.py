import json
import uuid

import pytest

from app import db
from app.policies import POLICY_VERSION, default_policy_config
from app.storage import ObjectStoreUnavailable, ResilientObjectRepository


@pytest.fixture(autouse=True)
def restore_application_repository(monkeypatch):
    yield
    monkeypatch.undo()
    db.reset_repository_for_tests()
    db.init_db()
    db.ensure_policy(default_policy_config(), POLICY_VERSION)


def _event(**overrides):
    value = {
        "event_id": str(uuid.uuid4()),
        "occurred_at": db.utcnow(),
        "user_name": "storage-user",
        "device_name": "storage-device",
        "organization": "storage-tenant",
        "source": "test",
        "profile_name": "Storage Test",
        "profile_id": "profile-1",
        "policy_version": POLICY_VERSION,
        "hook_event": "UserPromptSubmit",
        "decision": "allowed",
        "severity": "info",
        "prompt_content": "safe prompt",
    }
    value.update(overrides)
    return value


def test_local_object_repository_is_durable_source_and_rebuilds_index(tmp_path, monkeypatch):
    monkeypatch.setenv("OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("OBJECT_STORE_DIR", str(tmp_path / "objects"))
    monkeypatch.setenv("COS_PREFIX", "tenant-a/v1")
    db.reset_repository_for_tests()
    db.init_db()
    db.ensure_policy(default_policy_config(), POLICY_VERSION)

    event = _event()
    assert db.insert_event(event) is True
    assert db.insert_event(event) is False
    assert list((tmp_path / "objects" / "tenant-a" / "v1" / "events" / "by-time").rglob(f"{event['event_id']}.json"))
    assert (tmp_path / "objects" / "tenant-a" / "v1" / "outbox" / "pending" / f"{event['event_id']}.json").exists()

    db.reset_repository_for_tests()
    db.init_db()
    restored = db.query_events({"user": "storage-user"})
    assert len(restored) == 1
    assert restored[0]["event_id"] == event["event_id"]
    assert db.active_policy()["version"] == POLICY_VERSION
    db.reset_repository_for_tests()


def test_large_content_is_split_behind_cos_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("OBJECT_STORE_DIR", str(tmp_path / "objects"))
    monkeypatch.setenv("COS_PREFIX", "tenant-b/v1")
    monkeypatch.setenv("COS_INLINE_CONTENT_MAX", "32")
    db.reset_repository_for_tests()
    db.init_db()
    event = _event(prompt_content="x" * 200)
    assert db.insert_event(event)

    envelope_path = next((tmp_path / "objects" / "tenant-b" / "v1" / "events").rglob(f"{event['event_id']}.json"))
    envelope = json.loads(envelope_path.read_text())
    assert envelope["schema_version"] == 1
    assert envelope["prompt_content"] is None
    assert envelope["content_ref"].startswith("content/")
    listed = db.query_events({"user": "storage-user"})[0]
    assert "prompt_content" not in listed
    assert "content_ref" not in listed
    hydrated = db.get_event(event["event_id"])
    assert hydrated["prompt_content"] == "x" * 200
    db.reset_repository_for_tests()


class _UnavailableRepository:
    mode = "cos"

    def put_json(self, key, value, *, immutable=False):
        raise ConnectionError("offline")

    def get_json(self, key):
        raise ConnectionError("offline")

    def list_json(self, prefix):
        raise ConnectionError("offline")


class _WriteUnavailableRepository:
    def __init__(self, delegate):
        self.delegate = delegate
        self.mode = delegate.mode

    def put_json(self, key, value, *, immutable=False):
        raise ConnectionError("writes offline")

    def get_json(self, key):
        return self.delegate.get_json(key)

    def list_json(self, prefix):
        return self.delegate.list_json(prefix)


def test_retry_queue_is_bounded_and_reports_degraded_state():
    repository = ResilientObjectRepository(_UnavailableRepository(), prefix="test", queue_limit=2)
    repository.put_json("one.json", {"id": 1}, immutable=True)
    repository.put_json("two.json", {"id": 2}, immutable=True)
    with pytest.raises(ObjectStoreUnavailable):
        repository.put_json("three.json", {"id": 3}, immutable=True)
    health = repository.health()
    assert health["status"] == "degraded"
    assert health["pending_writes"] == 2
    assert health["last_error_type"] == "ConnectionError"


def _use_repository(repository):
    db._repository = repository


def test_control_plane_writes_never_succeed_from_retry_queue(tmp_path, monkeypatch):
    monkeypatch.setenv("OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("OBJECT_STORE_DIR", str(tmp_path / "objects"))
    monkeypatch.setenv("COS_PREFIX", "control/v1")
    db.reset_repository_for_tests()
    db.init_db()
    db.ensure_policy(default_policy_config(), POLICY_VERSION)
    original_draft = db.draft_policy()

    unavailable = ResilientObjectRepository(_UnavailableRepository(), prefix="control/v1", queue_limit=20)
    _use_repository(unavailable)
    changed = default_policy_config()
    changed["name"] = "Unsaved change"
    with pytest.raises(ObjectStoreUnavailable):
        db.save_policy_draft(changed, str(original_draft["revision"]), "tester")
    assert db.draft_policy() == original_draft
    assert unavailable.health()["pending_writes"] == 0

    with pytest.raises(ObjectStoreUnavailable):
        db.publish_policy_draft("99.0.0", "tester")
    assert db.active_policy()["version"] == POLICY_VERSION
    assert db.latest_rollout() is None


def test_rollout_transition_requires_durable_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("OBJECT_STORE_DIR", str(tmp_path / "objects"))
    monkeypatch.setenv("COS_PREFIX", "rollout/v1")
    db.reset_repository_for_tests()
    db.init_db()
    db.ensure_policy(default_policy_config(), POLICY_VERSION)
    candidate, rollout_id = db.publish_policy_draft("99.0.0", "tester")
    assert candidate["status"] == "staged"
    assert db.active_policy()["version"] == POLICY_VERSION
    assert db.latest_rollout()["status"] == "pending"

    durable_delegate = db._repository.delegate
    unavailable = ResilientObjectRepository(
        _WriteUnavailableRepository(durable_delegate), prefix="rollout/v1", queue_limit=20
    )
    _use_repository(unavailable)
    with pytest.raises(ObjectStoreUnavailable):
        db.update_rollout(rollout_id, "failed", error="MDM unavailable")
    assert db.latest_rollout()["status"] == "pending"
    with pytest.raises(ObjectStoreUnavailable):
        db.update_rollout(rollout_id, "succeeded", target_count=5)
    assert db.active_policy()["version"] == POLICY_VERSION
    assert db.latest_rollout()["status"] == "pending"
    assert unavailable.health()["pending_writes"] == 0


def test_staged_policy_activates_only_after_successful_rollout(tmp_path, monkeypatch):
    monkeypatch.setenv("OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("OBJECT_STORE_DIR", str(tmp_path / "objects"))
    monkeypatch.setenv("COS_PREFIX", "publication/v1")
    db.reset_repository_for_tests()
    db.init_db()
    db.ensure_policy(default_policy_config(), POLICY_VERSION)

    candidate, rollout_id = db.publish_policy_draft("99.0.0", "publisher")
    assert candidate["status"] == "staged"
    assert db.active_policy()["version"] == POLICY_VERSION
    db.update_rollout(rollout_id, "failed", error="profile rejected")
    assert db.active_policy()["version"] == POLICY_VERSION
    assert db.latest_rollout()["status"] == "failed"

    _, successful_rollout_id = db.publish_policy_draft("99.0.1", "publisher")
    db.update_rollout(successful_rollout_id, "succeeded", target_count=7)
    assert db.active_policy()["version"] == "99.0.1"
    assert db.latest_rollout()["status"] == "submitted"
    assert db.latest_rollout()["target_count"] == 7
    active_path = tmp_path / "objects" / "publication" / "v1" / "policies" / "active.json"
    assert json.loads(active_path.read_text())["version"] == "99.0.1"


def test_event_ingestion_retains_best_effort_degraded_queue():
    unavailable = ResilientObjectRepository(_UnavailableRepository(), prefix="events/v1", queue_limit=20)
    _use_repository(unavailable)
    assert db.insert_event(_event()) is True
    health = unavailable.health()
    assert health["status"] == "degraded"
    assert health["pending_writes"] >= 3
