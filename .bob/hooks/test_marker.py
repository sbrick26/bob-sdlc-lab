"""PostToolUse on execute_command: remember that the tests passed in this session."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lab

p = _lab.read_payload()
cmd = str((p.get("tool_input") or {}).get("command", ""))
out = str(p.get("tool_response", ""))
if "pytest" in cmd:
    passed = re.search(r"\b(\d+) passed\b", out) and not re.search(r"\b\d+ (failed|error)", out)
    path = _lab.marker_path("tests-passed")
    if passed:
        open(path, "w").write(cmd + "\n")
    elif os.path.exists(path):
        os.remove(path)
