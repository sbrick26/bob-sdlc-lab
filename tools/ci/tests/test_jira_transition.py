import importlib.util
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("jira_transition", os.path.join(os.path.dirname(HERE), "jira_transition.py"))
jt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jt)

ENV = {"JIRA_BASE_URL": "https://example.atlassian.net", "JIRA_EMAIL": "ci@example.com", "JIRA_API_TOKEN": "t"}


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeJira:
    def __init__(self, transitions):
        self.transitions = transitions
        self.calls = []

    def __call__(self, req, timeout=None):
        body = json.loads(req.data.decode()) if req.data else None
        self.calls.append((req.get_method(), req.full_url, body))
        if req.get_method() == "GET":
            return FakeResp(json.dumps({"transitions": self.transitions}).encode())
        return FakeResp(b"")


def test_skips_without_secrets(capsys):
    assert jt.run("LAB-1", "https://x/pr/1", env={}) == 0
    assert "not set, skipping" in capsys.readouterr().out


def test_moves_to_done_and_comments():
    fake = FakeJira([{"id": "11", "name": "In Review"}, {"id": "31", "name": "Done"}])
    assert jt.run("LAB-2", "https://github.com/o/r/pull/5", env=ENV, opener=fake) == 0
    methods = [c[0] for c in fake.calls]
    assert methods == ["GET", "POST", "POST"]
    assert fake.calls[1][2] == {"transition": {"id": "31"}}
    assert fake.calls[2][1].endswith("/rest/api/3/issue/LAB-2/comment")
    assert "https://github.com/o/r/pull/5" in json.dumps(fake.calls[2][2])


def test_matches_target_status_name():
    fake = FakeJira([{"id": "41", "name": "Close it", "to": {"name": "Done"}}])
    assert jt.run("LAB-3", "u", env=ENV, opener=fake) == 0
    assert fake.calls[1][2] == {"transition": {"id": "41"}}


def test_no_done_transition_returns_error():
    fake = FakeJira([{"id": "11", "name": "In Review"}])
    assert jt.run("LAB-4", "u", env=ENV, opener=fake) == 1
    assert len(fake.calls) == 1
