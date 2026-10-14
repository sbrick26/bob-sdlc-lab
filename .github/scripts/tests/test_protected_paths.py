import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "protected_paths.py")


def run(paths, allow=""):
    env = dict(os.environ, ALLOW_PROTECTED=allow)
    return subprocess.run([sys.executable, SCRIPT], input="\n".join(paths), capture_output=True,
                          text=True, env=env).returncode


def test_clean_diff_passes():
    assert run(["fieldops/app.py", "tests/test_x.py", "plans/LAB-1.md", "toolsx/a.py"]) == 0


def test_protected_fails():
    for p in [".bob/settings.json", ".github/workflows/x.yml", "governance/pr-checklist.yaml",
              ".github/scripts/parse_verdict.py"]:
        assert run(["fieldops/app.py", p]) == 1, p


def test_allowed_passes():
    assert run([".bob/settings.json"], allow="true") == 0
