#!/usr/bin/env python3

import os
import plistlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.policies import POLICY_VERSION, default_policy_config  # noqa: E402
from app.profile import build_profile  # noqa: E402

OUTPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tmp" / "bob-governance.mobileconfig"
APP_NAME = os.environ.get("APP_NAME", "bob-governance")
PROFILE_ID = os.environ.get("GOVERNANCE_PROFILE_ID", "100001")
KEYCHAIN_SERVICE = os.environ.get("INGEST_KEYCHAIN_SERVICE", "bob-governance-ingest-token")


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


url = os.environ.get("GOVERNANCE_URL") or run(
    "ibmcloud", "ce", "app", "get", "--name", APP_NAME, "--output", "url"
)
token = run(
    "security", "find-generic-password", "-a", os.environ["USER"],
    "-s", KEYCHAIN_SERVICE, "-w",
)
content = build_profile(
    config=default_policy_config(),
    version=POLICY_VERSION,
    api_url=url,
    ingest_token=token,
    profile_id=PROFILE_ID,
)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_bytes(content)
OUTPUT.chmod(0o600)

loaded = plistlib.loads(content)
assert loaded["PayloadIdentifier"] == "com.ibm.bob.governance"
print(f"Generated {OUTPUT} for {url} (credential embedded but not printed)")
