#!/usr/bin/env python3
"""Bob silently ignores a skill or mode file it cannot parse, so parse them all here.

Checks every .bob/plugins/bob-sdlc/skills/*/SKILL.md frontmatter, custom_modes.yaml,
.bob/settings.json, mcp.json and .bob/governance/*.yaml. Standard library plus pyyaml.
Exit 0 when all parse; exit 1 with one line per broken file otherwise.
"""
import glob
import json
import os
import re
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PLUGIN = os.path.join(ROOT, ".bob", "plugins", "bob-sdlc")


def rel(path):
    return os.path.relpath(path, ROOT)


def check_skills(errors):
    skills = sorted(glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md")))
    if not skills:
        errors.append("%s: no skills found" % rel(os.path.join(PLUGIN, "skills")))
    for path in skills:
        text = open(path, encoding="utf-8").read()
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
        if not m:
            errors.append("%s: no frontmatter (--- block at the top)" % rel(path))
            continue
        try:
            data = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            errors.append("%s: frontmatter is not valid YAML: %s" % (rel(path), str(e).replace("\n", " ")))
            continue
        if data.get("name") != os.path.basename(os.path.dirname(path)):
            errors.append("%s: name must match the folder name" % rel(path))
        if not (isinstance(data.get("description"), str) and data["description"].strip()):
            errors.append("%s: description missing" % rel(path))
    return len(skills)


def check_modes(errors):
    path = os.path.join(PLUGIN, "custom_modes.yaml")
    try:
        data = yaml.safe_load(open(path, encoding="utf-8"))
        slugs = [m["slug"] for m in data["customModes"]]
    except Exception as e:
        errors.append("%s: does not parse: %s" % (rel(path), str(e).replace("\n", " ")))
        return
    if len(slugs) != len(set(slugs)):
        errors.append("%s: duplicate mode slugs %s" % (rel(path), slugs))
    missing = {"sdlc", "sdlc-plan", "sdlc-build", "sdlc-review"} - set(slugs)
    if missing:
        errors.append("%s: missing modes %s" % (rel(path), sorted(missing)))


def check_json(errors):
    for path in (os.path.join(ROOT, ".bob", "settings.json"), os.path.join(PLUGIN, "mcp.json")):
        try:
            json.load(open(path, encoding="utf-8"))
        except Exception as e:
            errors.append("%s: not valid JSON: %s" % (rel(path), e))


def check_governance(errors):
    for path in sorted(glob.glob(os.path.join(ROOT, ".bob", "governance", "*.yaml"))):
        try:
            yaml.safe_load(open(path, encoding="utf-8"))
        except Exception as e:
            errors.append("%s: does not parse: %s" % (rel(path), str(e).replace("\n", " ")))


def main():
    errors = []
    n = check_skills(errors)
    check_modes(errors)
    check_json(errors)
    check_governance(errors)
    if errors:
        for e in errors:
            print("check_plugin_files: BROKEN " + e)
        return 1
    print("check_plugin_files: ok (%d skills, custom_modes.yaml, settings.json, mcp.json, governance files)" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
