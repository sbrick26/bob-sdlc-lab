"""Bob silently ignores a skill or mode file it cannot parse, so parse them all here."""
import glob, os, re
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PLUGIN = os.path.join(ROOT, ".bob", "plugins", "bob-sdlc")


def test_every_skill_has_valid_frontmatter():
    skills = glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md"))
    assert skills
    for path in skills:
        text = open(path, encoding="utf-8").read()
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
        assert m, f"{path}: no frontmatter"
        data = yaml.safe_load(m.group(1))
        assert data.get("name") == os.path.basename(os.path.dirname(path)), f"{path}: name must match the folder"
        assert isinstance(data.get("description"), str) and data["description"].strip(), f"{path}: description missing"


def test_modes_file_parses_and_slugs_are_unique():
    data = yaml.safe_load(open(os.path.join(PLUGIN, "custom_modes.yaml"), encoding="utf-8"))
    slugs = [m["slug"] for m in data["customModes"]]
    assert len(slugs) == len(set(slugs))
    assert {"sdlc", "sdlc-plan", "sdlc-build", "sdlc-review"} <= set(slugs)


def test_settings_and_mcp_are_json():
    import json
    json.load(open(os.path.join(ROOT, ".bob", "settings.json")))
    json.load(open(os.path.join(PLUGIN, "mcp.json")))
