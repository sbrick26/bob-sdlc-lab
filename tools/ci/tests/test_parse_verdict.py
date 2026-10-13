import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "parse_verdict.py")
FIX = os.path.join(HERE, "fixtures")


def run(name, *extra):
    p = subprocess.run([sys.executable, SCRIPT, os.path.join(FIX, name), *extra],
                       capture_output=True, text=True)
    return p.returncode, json.loads(p.stdout)


def test_pass_json_ignores_template_line():
    rc, out = run("review_pass.json")
    assert rc == 0
    assert out["verdict"] == "PASS"
    assert (out["criteria_met"], out["criteria_total"]) == (3, 3)
    assert (out["tests_passed"], out["tests_total"]) == (7, 7)
    assert out["blocking"] == 0
    assert out["findings"][0]["severity"] == "advisory"
    assert out["rules"] == "ok"


def test_fail_stream_json():
    rc, out = run("review_fail.jsonl")
    assert rc == 2
    assert out["verdict"] == "FAIL"
    assert out["blocking"] == 2
    assert len(out["findings"]) == 3
    assert (out["tests_passed"], out["tests_total"]) == (4, 5)
    assert out["rules"] == "03-personal-data.md"


def test_no_verdict_fails_closed(tmp_path):
    md = tmp_path / "c.md"
    rc, out = run("review_none.json", "--markdown", str(md))
    assert rc == 3
    assert out["verdict"] == "NONE"
    body = md.read_text()
    assert "<!-- sdlc-gate:bob-review -->" in body and "fails closed" in body


def test_plain_text_bold_and_tests_not_run():
    rc, out = run("review_text.txt")
    assert rc == 0
    assert out["tests_total"] is None
    assert out["findings"] == []


def test_missing_file_fails_closed():
    rc, out = run("does-not-exist.json")
    assert rc == 3


def test_markdown_has_marker(tmp_path):
    md = tmp_path / "c.md"
    rc, _ = run("review_fail.jsonl", "--markdown", str(md), "--meta", "Ticket LAB-4")
    text = md.read_text()
    assert rc == 2
    assert text.startswith("<!-- sdlc-gate:bob-review -->")
    assert "**Verdict: FAIL**" in text and "| Blocking findings | 2 |" in text
    assert "Ticket LAB-4" in text
