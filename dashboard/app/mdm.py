from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
import uuid


class MDMNotConfigured(RuntimeError):
    pass


def _request(method: str, path: str, body: bytes | None = None, content_type: str | None = None) -> tuple[int, bytes]:
    key = (os.environ.get("SIMPLEMDM_API_KEY") or "").strip()
    if not key:
        raise MDMNotConfigured("Managed deployment credentials are not configured.")
    base = (os.environ.get("SIMPLEMDM_API_BASE") or "https://a.simplemdm.com/api/v1").rstrip("/")
    token = base64.b64encode(f"{key}:".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read(2048).decode("utf-8", "replace")
        raise RuntimeError(f"Managed deployment request failed with HTTP {exc.code}: {detail}") from exc


def _multipart(fields: dict[str, str], filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"governance-{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode(), b"\r\n",
        ])
    parts.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="mobileconfig"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: application/x-apple-aspen-config\r\n\r\n",
        content, b"\r\n", f"--{boundary}--\r\n".encode(),
    ])
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def publish_profile(profile: bytes) -> dict[str, int | str]:
    profile_id = os.environ.get("SIMPLEMDM_PROFILE_ID", "100001")
    group_id = os.environ.get("SIMPLEMDM_GROUP_ID", "200001")
    body, content_type = _multipart(
        {
            "name": "Bob Governance",
            "declarative": "false",
            "user_scope": "false",
            "allowed_platforms[]": "macos",
        },
        "bob-governance.mobileconfig",
        profile,
    )
    status, _ = _request("PATCH", f"/custom_configuration_profiles/{profile_id}", body, content_type)
    if status != 200:
        raise RuntimeError(f"Managed profile update returned HTTP {status}.")
    sync_status, _ = _request("POST", f"/assignment_groups/{group_id}/sync_profiles", b"")
    if sync_status != 204:
        raise RuntimeError(f"Managed group synchronization returned HTTP {sync_status}.")
    return {"profile_id": profile_id, "assignment_group_id": group_id, "target_count": 0}
