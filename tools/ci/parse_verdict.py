#!/usr/bin/env python3
"""Parse the review verdict block out of a headless `bob run` result.

Input: a file path (or stdin) holding `bob run -f json` output, `-f stream-json`
lines, or plain text. Every string in the JSON is searched, so the exact JSON
shape does not matter. The LAST block that starts with `VERDICT: PASS` or
`VERDICT: FAIL` wins. The template line `VERDICT: PASS | FAIL` never matches.

Output: one JSON object on stdout:
  {"verdict", "criteria_met", "criteria_total", "findings": [{"severity","text"}],
   "blocking", "rules", "tests_passed", "tests_total"}
With --markdown PATH it also writes the PR comment body.

Exit codes (fail closed):
  0  verdict PASS
  2  verdict FAIL
  3  no verdict found (the workflow treats this as a failure)
Standard library only.
"""
import argparse
import json
import re
import sys

VERDICT_RE = re.compile(r"^[\s>*#`_-]*VERDICT\s*:\s*\**\s*(PASS|FAIL)\b[\s*`_.]*$", re.M)
CRITERIA_RE = re.compile(r"^[\s>*`_-]*CRITERIA\s*:\s*\**\s*(\d+)\s*/\s*(\d+)", re.M)
TESTS_RE = re.compile(r"^[\s>*`_-]*TESTS\s*:\s*\**\s*(?:(\d+)\s*/\s*(\d+)|(not run))", re.M | re.I)
RULES_RE = re.compile(r"^[\s>*`_-]*RULES\s*:\s*\**\s*(.+?)\s*$", re.M)
FINDING_RE = re.compile(r"^\s*[-*]\s*\[(blocking|advisory)\]\s*(.+?)\s*$", re.M | re.I)
SECTION_RE = re.compile(r"^[\s>*`_-]*(RULES|TESTS|VERDICT|CRITERIA)\s*:", re.M)


def collect_strings(obj, out):
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_strings(v, out)


def to_text(raw):
    """Turn json, stream-json (one object per line) or plain text into text."""
    raw = raw.strip()
    if not raw:
        return ""
    try:
        parts = []
        collect_strings(json.loads(raw), parts)
        return "\n".join(parts)
    except json.JSONDecodeError:
        pass
    parts, any_json = [], False
    for line in raw.splitlines():
        try:
            collect_strings(json.loads(line), parts)
            any_json = True
        except json.JSONDecodeError:
            parts.append(line)
    return "\n".join(parts) if any_json else raw


def parse(raw):
    text = to_text(raw)
    matches = list(VERDICT_RE.finditer(text))
    if not matches:
        return None
    block = text[matches[-1].start():]
    result = {"verdict": matches[-1].group(1), "criteria_met": None, "criteria_total": None,
              "findings": [], "blocking": 0, "rules": None,
              "tests_passed": None, "tests_total": None}
    m = CRITERIA_RE.search(block)
    if m:
        result["criteria_met"], result["criteria_total"] = int(m.group(1)), int(m.group(2))
    m = TESTS_RE.search(block)
    if m and m.group(1):
        result["tests_passed"], result["tests_total"] = int(m.group(1)), int(m.group(2))
    m = RULES_RE.search(block)
    if m:
        result["rules"] = m.group(1)
    # Findings: lines between FINDINGS: and the next section header.
    f = re.search(r"^[\s>*`_-]*FINDINGS\s*:(.*)$", block, re.M)
    if f:
        rest = block[f.end():]
        nxt = SECTION_RE.search(rest)
        area = f.group(1) + "\n" + (rest[:nxt.start()] if nxt else rest)
        for fm in FINDING_RE.finditer(area):
            result["findings"].append({"severity": fm.group(1).lower(), "text": fm.group(2)})
    result["blocking"] = sum(1 for x in result["findings"] if x["severity"] == "blocking")
    return result


def markdown(result, raw, meta):
    marker = "<!-- sdlc-gate:bob-review -->"
    head = [marker, "## SDLC gate: review", ""]
    if meta:
        head.append(meta)
        head.append("")
    if result is None:
        tail = to_text(raw)[-1500:]
        return "\n".join(head + ["**Verdict: NONE** (no VERDICT line, the gate fails closed)", "",
                                 "Output tail:", "```", tail, "```", ""])
    lines = head + ["**Verdict: %s**" % result["verdict"], "",
                    "| Item | Value |", "|---|---|"]
    if result["criteria_total"] is not None:
        lines.append("| Criteria | %d/%d |" % (result["criteria_met"], result["criteria_total"]))
    if result["tests_total"] is not None:
        lines.append("| Tests | %d/%d |" % (result["tests_passed"], result["tests_total"]))
    lines.append("| Rules | %s |" % (result["rules"] or "not reported"))
    lines.append("| Blocking findings | %d |" % result["blocking"])
    lines.append("")
    if result["findings"]:
        lines.append("Findings:")
        for x in result["findings"]:
            lines.append("- [%s] %s" % (x["severity"], x["text"]))
    else:
        lines.append("No findings.")
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", nargs="?", help="review output file (default: stdin)")
    ap.add_argument("--markdown", help="write the PR comment body to this path")
    ap.add_argument("--meta", default="", help="one line added under the comment title")
    args = ap.parse_args(argv)
    if args.input:
        try:
            with open(args.input, encoding="utf-8", errors="replace") as fh:
                raw = fh.read()
        except OSError:
            raw = ""
    else:
        raw = sys.stdin.read()
    result = parse(raw)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(markdown(result, raw, args.meta))
    if result is None:
        print(json.dumps({"verdict": "NONE", "criteria_met": None, "criteria_total": None,
                          "findings": [], "blocking": 0, "rules": None,
                          "tests_passed": None, "tests_total": None}))
        print("FAIL CLOSED: no VERDICT line in the review output.", file=sys.stderr)
        return 3
    print(json.dumps(result))
    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
