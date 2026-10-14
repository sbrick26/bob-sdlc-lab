#!/usr/bin/env python3
"""Reset lab data: delete every object under the configured store prefix.

Local mode (default): deletes the files under OBJECT_STORE_DIR (or
DATA_DIR/objects) / COS_PREFIX and prints each path it removed.
COS mode (OBJECT_STORE_MODE=cos or COS_BUCKET set): prints the ibmcloud cos
command to run. It does not run it.

Usage:
  DATA_DIR=./data .venv/bin/python scripts/reset-lab.py
"""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path


def main() -> int:
    prefix = os.environ.get("COS_PREFIX", "bob-governance/v1").strip("/")
    bucket = os.environ.get("COS_BUCKET") or os.environ.get("IBM_COS_BUCKET") or ""
    mode = (os.environ.get("OBJECT_STORE_MODE") or ("cos" if bucket else "local")).lower()
    if mode == "cos":
        b, p = shlex.quote(bucket or "<bucket>"), shlex.quote(prefix + "/")
        print("COS mode: not deleting. Run this to delete every object under the prefix:")
        print(
            f"ibmcloud cos objects --bucket {b} --prefix {p} --output json"
            " | jq -r '.Contents[]?.Key'"
            f" | while read -r key; do ibmcloud cos object-delete --bucket {b} --key \"$key\" --force; done"
        )
        return 0
    if mode != "local":
        print("OBJECT_STORE_MODE must be 'cos' or 'local'", file=sys.stderr)
        return 2
    root = Path(
        os.environ.get("OBJECT_STORE_DIR")
        or os.path.join(os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")), "objects")
    ).resolve()
    base = (root / prefix).resolve()
    if base != root and root not in base.parents:
        print(f"refusing: {base} is outside {root}", file=sys.stderr)
        return 2
    removed = 0
    if base.exists():
        for path in sorted(base.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
                print(f"removed {path}")
                removed += 1
            elif path.is_dir():
                path.rmdir()
    print(f"{removed} object(s) removed under {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
