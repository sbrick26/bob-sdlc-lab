from __future__ import annotations

import csv
import hmac
import io
import hashlib
import asyncio
import json
import os
import re
import shlex
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db
from . import lab
from . import mdm
from . import metrics
from . import summaries
from . import detail
from .stream import HEARTBEAT_SECONDS, broker, event_message
from .policies import PACKAGE_ALLOWLIST, POLICY_VERSION, RULES, default_policy_config, prompt_rule_id, rule
from .profile import build_profile
from .storage import ObjectStoreUnavailable
from .ui import INDEX_HTML

@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    db.ensure_policy(default_policy_config(), POLICY_VERSION)
    async def flush_storage() -> None:
        while True:
            await asyncio.sleep(30)
            await asyncio.to_thread(db.flush_pending_writes, 100)

    task = asyncio.create_task(flush_storage())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Governance", version="1.0.0", redoc_url=None, lifespan=lifespan)
dashboard_security = HTTPBasic(auto_error=False)
FRONTEND_DIST = PurePath(__file__).parent.parent / "frontend" / "dist"
if os.path.isdir(FRONTEND_DIST / "assets"):
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.middleware("http")
async def protect_governance_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/api/v1/stream":
        response.headers["Cache-Control"] = "no-cache, no-transform"
    elif request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

FORBIDDEN_KEYS = {
    "prompt", "raw_prompt", "tool_input", "raw_tool_input", "tool_output",
    "tool_response", "command", "arguments", "environment", "env", "secret",
    "token", "api_key", "password", "prompt_content", "tool_input_content",
    "tool_output_content", "response_content",
}
MAX_BODY = 262_144
SAFE_TEXT = re.compile(r"^[^\x00-\x08\x0b\x0c\x0e-\x1f]{0,512}$")
MAX_CONTENT = 16_000

SECRET_PATTERNS = [
    ("sk-prefixed API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{12,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("Stripe secret key", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("labeled secret", re.compile(
        r"(?i)(?P<prefix>[\"']?(?:api[_ -]?key|token|secret|password|client[_ -]?secret)"
        r"[\"']?\s*[:=]\s*[\"']?)(?P<value>(?!REDACTED|example|changeme|\$\{|\$[A-Z_]"
        r"|process\.env|os\.(?:environ|getenv)|env\.|secret://|vault://|<)"
        r"[A-Za-z0-9._~+/=-]{16,})"
    )),
    ("labeled secret", re.compile(
        r"(?is)(?P<prefix>\b(?:api[_ -]?key|token|secret|password|client[_ -]?secret)\b"
        r"(?:(?!\n).){0,80}?)(?P<value>(?!REDACTED|example|changeme|\$\{|\$[A-Z_]"
        r"|process\.env|os\.(?:environ|getenv)|env\.|secret://|vault://|<)"
        r"(?=[A-Za-z0-9]{24,}\b)(?=[A-Za-z0-9]*[A-Z])(?=[A-Za-z0-9]*[a-z])"
        r"(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{24,})"
    )),
]
MANAGED_REFERENCE_PATTERN = re.compile(
    r"(?i)\$\{[A-Z_][A-Z0-9_]*\}|\$[A-Z_][A-Z0-9_]*|"
    r"process\.env\.[A-Z_][A-Z0-9_]*|os\.environ\[[^\]]+\]|os\.getenv\([^)]*\)|"
    r"(?:vault|secret)://[A-Z0-9._~/-]+|"
    r"(?:environment|env)\s+(?:variable|var)\s+[A-Z_][A-Z0-9_]*"
)


def ingest_token() -> str:
    return (os.environ.get("INGEST_TOKEN") or "").strip()


def require_ingest(authorization: str | None = Header(default=None)) -> None:
    expected = ingest_token()
    if not expected:
        raise HTTPException(503, "ingest is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    supplied = authorization[7:].strip()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(403, "invalid bearer token")


def require_dashboard(credentials: HTTPBasicCredentials | None = Depends(dashboard_security)) -> str:
    expected_user = (os.environ.get("DASHBOARD_USER") or "governance").strip()
    expected_password = (os.environ.get("DASHBOARD_PASSWORD") or "").strip()
    valid = bool(
        expected_password
        and credentials
        and hmac.compare_digest(credentials.username.encode(), expected_user.encode())
        and hmac.compare_digest(credentials.password.encode(), expected_password.encode())
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="dashboard authentication required",
            headers={"WWW-Authenticate": 'Basic realm="Governance"'},
        )
    return credentials.username


def reject_sensitive_shape(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in FORBIDDEN_KEYS:
                raise HTTPException(422, f"content field is not accepted: {path}{key}")
            reject_sensitive_shape(child, f"{path}{key}.")
    elif isinstance(value, list):
        for child in value:
            reject_sensitive_shape(child, path)


def clean_event(body: dict[str, Any], *, allow_content: bool = False) -> dict[str, Any]:
    if not allow_content:
        reject_sensitive_shape(body)
    required = (
        "event_id", "occurred_at", "user_name", "device_name", "source",
        "profile_name", "policy_version", "hook_event", "decision", "severity",
    )
    missing = [key for key in required if not body.get(key)]
    if missing:
        raise HTTPException(422, f"missing required fields: {', '.join(missing)}")
    if body["decision"] not in db.ALLOWED_DECISIONS:
        raise HTTPException(422, "invalid decision")
    if body["severity"] not in db.ALLOWED_SEVERITIES:
        raise HTTPException(422, "invalid severity")
    event: dict[str, Any] = {}
    for field in db.FIELDS:
        value = body.get(field)
        if field == "duration_ms":
            event[field] = None if value is None else min(max(int(value), 0), 30_000)
        elif field == "tool_duration_ms":
            event[field] = None if value is None else min(max(int(value), 0), 86_400_000)
        elif field in {"finding_count", "content_logged"}:
            event[field] = min(max(int(value or 0), 0), 10_000)
        elif field == "lab_data":
            event[field] = value if isinstance(value, dict) else None
        elif field == "lab_pr":
            event[field] = None if value is None else min(max(int(value), 0), 10_000_000)
        elif field == "lab_cost":
            event[field] = None if value is None else float(value)
        elif field == "hook_rtt_prev_ms":
            event[field] = None if value is None else min(max(int(value), 0), 600_000)
        elif field == "check_ms":
            event[field] = None if value is None else round(min(max(float(value), 0.0), 60_000.0), 3)
        elif field in {"lab_tokens", "lab_turns"}:
            event[field] = None if value is None else min(max(int(value), 0), 10**12)
        elif field in {"prompt_content", "tool_input_content", "tool_output_content", "response_content"}:
            event[field] = str(value)[:MAX_CONTENT] if value is not None else None
        elif value is None:
            event[field] = None
        else:
            text = str(value).strip()
            if not SAFE_TEXT.match(text):
                raise HTTPException(422, f"invalid text in {field}")
            event[field] = text[:512]
    return event


def redact(value: Any) -> tuple[str, list[str]]:
    if value is None:
        return "", []
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    managed_references: list[str] = []

    def stash_reference(match: re.Match[str]) -> str:
        managed_references.append(match.group(0))
        return f"<MANAGED_REFERENCE_{len(managed_references) - 1}>"

    text = MANAGED_REFERENCE_PATTERN.sub(stash_reference, text)
    hits: list[str] = []
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            hits.append(name)
            if name == "labeled secret":
                text = pattern.sub(lambda match: f"{match.group('prefix')}[REDACTED: {name}]", text)
            else:
                text = pattern.sub(f"[REDACTED: {name}]", text)
    for index, reference in enumerate(managed_references):
        text = text.replace(f"<MANAGED_REFERENCE_{index}>", reference)
    return text[:MAX_CONTENT], sorted(set(hits))


STORED_TOKEN = re.compile(r"(?<![A-Za-z0-9])(?=[A-Za-z0-9_+=-]*\d)(?=[A-Za-z0-9_+=-]*[A-Za-z])[A-Za-z0-9_+=-]{24,}(?![A-Za-z0-9])")
STORED_PHONE = re.compile(r"\b\d{3}-\d{3}-\d{4}\b")


def mask_stored(text: str, phones: bool = True) -> str:
    """Mask long token-like strings and (optionally) US phone numbers, keeping their length."""
    if not text:
        return text
    marker = lambda match: f"[masked {len(match.group(0))} chars]"  # noqa: E731
    text = STORED_TOKEN.sub(marker, text)
    return STORED_PHONE.sub(marker, text) if phones else text


def bucket(length: int) -> str:
    if length == 0:
        return "0"
    if length < 64:
        return "1-63"
    if length < 256:
        return "64-255"
    if length < 1024:
        return "256-1023"
    if length < 4096:
        return "1024-4095"
    return "4096+"


def opaque(value: str) -> str:
    key = ingest_token().encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:20] if value else "unknown"


def _command_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("command", "cmd", "script"):
            if isinstance(value.get(key), str):
                return value[key]
    return value if isinstance(value, str) else ""


def _package_name(raw: str, ecosystem: str) -> str:
    value = raw.strip().strip("'\"")
    if ecosystem == "python":
        value = value.split(";", 1)[0].split("[", 1)[0]
        return re.split(r"[<>=!~]", value, maxsplit=1)[0].lower().replace("_", "-")
    if value.startswith("@"):
        slash = value.find("/")
        at = value.find("@", slash + 1) if slash >= 0 else -1
        return (value[:at] if at >= 0 else value).lower()
    return value.split("@", 1)[0].lower()


INSTALL_HINT = re.compile(r"\b(pip3?|npm|pnpm|yarn)\b|python3? -m pip")


def package_install_findings(
    value: Any, allowlist: dict[str, list[str]] | None = None
) -> tuple[str | None, list[str]]:
    """Return the ecosystem and requested packages not present in the active allowlist."""
    command = _command_text(value)
    if not command:
        return None, []
    findings: dict[str, set[str]] = {"python": set(), "node": set()}
    detected: list[str] = []
    segments = [segment.strip() for segment in re.split(r"(?:&&|\|\||[;|\n])", command) if segment.strip()]
    for segment in segments:
        try:
            tokens = shlex.split(segment)
        except ValueError:
            # Only an install-looking segment is a finding; a quote that spans a
            # split point in an ordinary command (git, echo) is not.
            if INSTALL_HINT.search(segment):
                findings["python"].add("unparseable-install-command")
                detected.append("python")
            continue
        for index, token in enumerate(tokens):
            base = PurePath(token).name.lower()
            ecosystem: str | None = None
            args_at = -1
            if base in {"pip", "pip3"} and index + 1 < len(tokens) and tokens[index + 1] == "install":
                ecosystem, args_at = "python", index + 2
            elif base in {"python", "python3"} and tokens[index + 1:index + 4] == ["-m", "pip", "install"]:
                ecosystem, args_at = "python", index + 4
            elif base in {"npm", "pnpm"} and index + 1 < len(tokens) and tokens[index + 1] in {"install", "i", "add"}:
                ecosystem, args_at = "node", index + 2
            elif base == "yarn" and index + 1 < len(tokens) and tokens[index + 1] in {"add", "install"}:
                ecosystem, args_at = "node", index + 2
            if ecosystem is None:
                continue
            detected.append(ecosystem)
            requested: list[str] = []
            args = tokens[args_at:]
            skip_value = False
            for arg_index, arg in enumerate(args):
                if skip_value:
                    skip_value = False
                    continue
                if arg in {"-r", "--requirement"} or arg.startswith(("-r", "--requirement=")):
                    findings[ecosystem].add("dependency-manifest")
                    if arg in {"-r", "--requirement"}:
                        skip_value = True
                    continue
                if arg in {"--index-url", "--extra-index-url", "--registry"}:
                    skip_value = True
                    continue
                if arg.startswith("-"):
                    continue
                if re.match(r"^\d*(>>?|<|&>)", arg) or arg in {"&", "2>&1"}:
                    # shell redirection (2>&1, >log, 2>/dev/null) is not a package
                    if re.fullmatch(r"\d*(>>?|<|&>)", arg):
                        skip_value = True
                    continue
                package = _package_name(arg, ecosystem)
                if package and not package.startswith((".", "/", "git+", "http://", "https://")):
                    requested.append(package)
                elif package:
                    findings[ecosystem].add("local-or-remote-source")
            if not requested and not findings[ecosystem]:
                findings[ecosystem].add("dependency-manifest")
            approved = {
                name.lower().replace("_", "-")
                for name in (allowlist or PACKAGE_ALLOWLIST).get(ecosystem, [])
            }
            findings[ecosystem].update(name for name in requested if name not in approved)

    if not detected:
        return None, []
    ecosystems = sorted(set(detected))
    combined = sorted({name for ecosystem in ecosystems for name in findings[ecosystem]})
    return "+".join(ecosystems), combined


PII_WRITE_TOOLS = {"write_file", "apply_diff", "insert_content", "search_and_replace"}
PII_PHONE = re.compile(r"\b\d{3}-\d{3}-\d{4}\b")
PII_EXEMPT_DIRS = ("data", "tests")
PATH_KEYS = ("path", "file_path", "target_file", "filePath", "file")
GIT_RULES = (
    (re.compile(r"(?:^|\s)--no-verify(?:\s|$)"), "Do not skip git hooks with --no-verify."),
    (re.compile(r"(?:^|\s)--force(?:\s|$)"), "Do not force-push or force git operations with --force."),
    (re.compile(r"\bpush\b(?:.*\s)?-f(?:\s|$)"), "Do not force-push with push -f."),
    (re.compile(r"\bpush\s+origin\s+(?:\S+:)?main\b"), "Do not push straight to main; open a pull request from a branch."),
)


def tool_input_path(value: Any) -> str | None:
    """Return the file path named in a tool input, if any."""
    if isinstance(value, dict):
        for key in PATH_KEYS:
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key].strip()[:512]
        if isinstance(value.get("args"), dict):
            return tool_input_path(value["args"])
    return None


def _strings(value: Any, skip: set[str]) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for key, child in value.items() if key not in skip for text in _strings(child, skip)]
    if isinstance(value, list):
        return [text for child in value for text in _strings(child, skip)]
    return []


def path_is_exempt_for_pii(path: str | None) -> bool:
    if not path:
        return False
    parts = [part for part in path.replace("\\", "/").split("/") if part not in {"", "."}]
    return any(part in PII_EXEMPT_DIRS for part in parts[:-1])


def pii_findings(tool_name: str | None, value: Any) -> list[str]:
    """GOV-PII-001: unmasked US phone numbers written outside data/ and tests/."""
    if tool_name not in PII_WRITE_TOOLS or path_is_exempt_for_pii(tool_input_path(value)):
        return []
    found: set[str] = set()
    for text in _strings(value, set(PATH_KEYS)):
        found.update(PII_PHONE.findall(text))
    return sorted(found)


def git_findings(tool_name: str | None, value: Any) -> list[str]:
    """GOV-GIT-001: reasons for each unsafe git pattern in an execute_command input."""
    if tool_name != "execute_command":
        return []
    command = _command_text(value)
    reasons: list[str] = []
    for segment in re.split(r"(?:&&|\|\||[;|\n])", command):
        if not re.search(r"\bgit\b", segment):
            continue
        for pattern, reason in GIT_RULES:
            if pattern.search(segment) and reason not in reasons:
                reasons.append(reason)
    return reasons


def runtime_rules() -> dict[str, dict[str, Any]]:
    active = db.active_policy()
    entries = (active or {}).get("config", {}).get("rules", [])
    return {str(entry.get("rule_id")): entry for entry in entries if isinstance(entry, dict)}


def active_policy_version() -> str:
    return str((db.active_policy() or {}).get("version") or POLICY_VERSION)


def session_context() -> str:
    enabled = [rule_id for rule_id, entry in runtime_rules().items() if entry.get("enabled", True)]
    capabilities = []
    if any(rule_id.startswith(("GOV-PROMPT", "GOV-TOOL", "GOV-POST", "GOV-RESP")) for rule_id in enabled):
        capabilities.append("credential safeguards")
    if "GOV-PKG-001" in enabled:
        capabilities.append("approved-package controls")
    controls = " and ".join(capabilities) or "managed monitoring"
    return (
        f"Managed Governance policy {active_policy_version()} is active with {controls}. "
        "Use managed secret references instead of literal credentials."
    )


def safe_occurred_at(value: str | None) -> str:
    if not value:
        return db.utcnow()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return db.utcnow()


def rule_enabled(entries: dict[str, dict[str, Any]], rule_id: str) -> bool:
    return bool(entries.get(rule_id, {"enabled": True}).get("enabled", True))


def safe_header(value: str | None, fallback: str) -> str:
    text = (value or fallback).strip()
    return re.sub(r"[^A-Za-z0-9@._ -]", "", text)[:120] or fallback


TICKET_PATTERN = re.compile(r"[A-Z][A-Z0-9]{0,9}-\d{1,6}")


def lab_ticket(value: str | None) -> str | None:
    text = (value or "").strip().upper()
    return text if TICKET_PATTERN.fullmatch(text) else None


def lab_role(value: str | None) -> str | None:
    text = (value or "").strip().lower()
    return text if text in lab.LAB_ROLES else None


def lab_branch(value: str | None) -> str | None:
    text = re.sub(r"[^A-Za-z0-9._/-]", "", (value or "").strip())[:120]
    return text or None


def lab_cost(value: str | None) -> float | None:
    try:
        cost = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return round(cost, 6) if 0 <= cost < 1_000_000 else None


def lab_count(value: str | None, maximum: int) -> int | None:
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return number if 0 <= number <= maximum else None


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_dashboard)])
def dashboard() -> Any:
    index = FRONTEND_DIST / "index.html"
    return FileResponse(str(index)) if os.path.isfile(index) else INDEX_HTML


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/storage/health", dependencies=[Depends(require_dashboard)])
def object_storage_health() -> dict[str, Any]:
    db.flush_pending_writes(100)
    return db.storage_health()


@app.post("/api/v1/events", dependencies=[Depends(require_ingest)])
async def ingest(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if len(raw) > MAX_BODY:
        raise HTTPException(413, "event is too large")
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(400, "body must be JSON") from exc
    items = body if isinstance(body, list) else [body]
    if not items or len(items) > 100 or not all(isinstance(item, dict) for item in items):
        raise HTTPException(422, "expected one event or a list of up to 100 events")
    accepted = inserted = 0
    for item in items:
        item = dict(item)
        for field in ("detail", "evidence"):
            if item.get(field) is not None:
                item[field] = redact(item[field])[0]
        event = clean_event(item)
        accepted += 1
        inserted += int(db.insert_event(event))
    return {"ok": True, "accepted": accepted, "inserted": inserted, "duplicates": accepted - inserted}


@app.post("/api/v1/hooks", dependencies=[Depends(require_ingest)])
async def ingest_hook(
    request: Request,
    x_governance_user: str | None = Header(None, alias="X-Governance-User"),
    x_governance_device: str | None = Header(None, alias="X-Governance-Device"),
    x_governance_device_id: str | None = Header(None, alias="X-Governance-Device-ID"),
    x_governance_profile: str | None = Header(None, alias="X-Governance-Profile"),
    x_governance_profile_id: str | None = Header(None, alias="X-Governance-Profile-ID"),
    x_governance_policy_version: str | None = Header(None, alias="X-Governance-Policy-Version"),
    x_bob_version: str | None = Header(None, alias="X-Bob-Version"),
    x_bob_channel: str | None = Header(None, alias="X-Bob-Channel"),
    x_governance_event_id: str | None = Header(None, alias="X-Governance-Event-ID"),
    x_governance_delivery: str | None = Header(None, alias="X-Governance-Delivery"),
    x_governance_occurred_at: str | None = Header(None, alias="X-Governance-Occurred-At"),
    x_governance_local_decision: str | None = Header(None, alias="X-Governance-Local-Decision"),
    x_governance_local_rule: str | None = Header(None, alias="X-Governance-Local-Rule"),
    x_governance_local_outcome: str | None = Header(None, alias="X-Governance-Local-Outcome"),
    x_governance_local_severity: str | None = Header(None, alias="X-Governance-Local-Severity"),
    x_lab_ticket: str | None = Header(None, alias="X-Lab-Ticket"),
    x_lab_role: str | None = Header(None, alias="X-Lab-Role"),
    x_lab_branch: str | None = Header(None, alias="X-Lab-Branch"),
    x_lab_cost: str | None = Header(None, alias="X-Lab-Cost"),
    x_lab_tokens: str | None = Header(None, alias="X-Lab-Tokens"),
    x_lab_turns: str | None = Header(None, alias="X-Lab-Turns"),
    x_governance_team: str | None = Header(None, alias="X-Governance-Team"),
    x_hook_prev_ms: str | None = Header(None, alias="X-Hook-Prev-Ms"),
) -> dict[str, Any]:
    """Receive Bob's native hook envelope, decide centrally, and store a redacted record."""
    started = time.perf_counter_ns()
    raw = await request.body()
    if len(raw) > MAX_BODY:
        return {"decision": "blocked", "reason": "Blocked by Governance: GOV-HOOK-001. The hook payload exceeded the inspection limit.", "context": ""}
    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise HTTPException(400, "hook body must be JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(422, "hook body must be an object")

    now_ms = int(time.time() * 1000)
    hook_event = str(payload.get("hook_event_name") or "Unknown")[:80]
    prompt_raw = payload.get("prompt") if isinstance(payload.get("prompt"), str) else ""
    tool_input_raw = payload.get("tool_input")
    tool_output_raw = payload.get("tool_response")
    response_raw = payload.get("last_assistant_message") if isinstance(payload.get("last_assistant_message"), str) else ""
    prompt_text, prompt_hits = redact(prompt_raw)
    tool_input_text, input_hits = redact(tool_input_raw)
    tool_output_text, output_hits = redact(tool_output_raw)
    response_text, response_hits = redact(response_raw)
    # Stored content is masked a second time at ingest: long token-like strings
    # and US phone numbers (not in files under data/ or tests/) become
    # "[masked N chars]", so the object store never holds them.
    input_path = tool_input_path(tool_input_raw)
    prompt_text = mask_stored(prompt_text)
    tool_input_text = mask_stored(tool_input_text, phones=not path_is_exempt_for_pii(input_path))
    tool_output_text = mask_stored(tool_output_text, phones=not path_is_exempt_for_pii(input_path))
    response_text = mask_stored(response_text)
    active_rules = runtime_rules()
    package_configuration = active_rules.get("GOV-PKG-001", {}).get("configuration", {})
    package_ecosystem, unapproved_packages = package_install_findings(
        tool_input_raw, package_configuration.get("allowlist")
    )
    tool_name = str(payload.get("tool_name") or "")[:120] or None
    phone_numbers = pii_findings(tool_name, tool_input_raw) if hook_event == "PreToolUse" else []
    git_reasons = git_findings(tool_name, tool_input_raw) if hook_event == "PreToolUse" else []

    decision = "allowed"
    severity = "info"
    rule_id = rule_name = None
    finding_count = 0
    reason = ""
    context = ""
    outcome = "completed"

    deferred = x_governance_delivery == "deferred"
    if hook_event == "UserPromptSubmit" and prompt_hits and rule_enabled(active_rules, prompt_rule_id(prompt_hits)):
        decision, severity = "blocked", "high"
        rule_id = prompt_rule_id(prompt_hits)
        rule_name = rule(rule_id)["name"]
        finding_count = len(prompt_hits)
        reason = f"Blocked by Governance: {rule_id}. Remove the credential and reference a managed secret instead."
        outcome = "prevented_before_model"
    elif hook_event == "PreToolUse" and input_hits and rule_enabled(active_rules, "GOV-TOOL-001"):
        decision, severity = "blocked", "high"
        rule_id, rule_name = "GOV-TOOL-001", rule("GOV-TOOL-001")["name"]
        finding_count = len(input_hits)
        reason = "Blocked by Governance: GOV-TOOL-001. Remove the credential from the tool input."
        outcome = "prevented_before_tool"
    elif hook_event == "PreToolUse" and unapproved_packages and rule_enabled(active_rules, "GOV-PKG-001"):
        decision, severity = "blocked", "high"
        rule_id, rule_name = "GOV-PKG-001", rule("GOV-PKG-001")["name"]
        finding_count = len(unapproved_packages)
        package_list = ", ".join(unapproved_packages)
        reason = f"Blocked by Governance: GOV-PKG-001. Not approved for {package_ecosystem}: {package_list}."
        outcome = "prevented_before_tool"
    elif hook_event == "PreToolUse" and phone_numbers and rule_enabled(active_rules, "GOV-PII-001"):
        decision, severity = "blocked", "high"
        rule_id, rule_name = "GOV-PII-001", rule("GOV-PII-001")["name"]
        finding_count = len(phone_numbers)
        reason = "Blocked by Governance: GOV-PII-001. Customer phone numbers must be masked as 415-555-****"
        outcome = "prevented_before_tool"
    elif hook_event == "PreToolUse" and git_reasons and rule_enabled(active_rules, "GOV-GIT-001"):
        decision, severity = "blocked", "high"
        rule_id, rule_name = "GOV-GIT-001", rule("GOV-GIT-001")["name"]
        finding_count = len(git_reasons)
        reason = "Blocked by Governance: GOV-GIT-001. " + " ".join(git_reasons)
        outcome = "prevented_before_tool"
    elif hook_event == "PostToolUse" and output_hits and rule_enabled(active_rules, "GOV-POST-001"):
        decision, severity = "observed", "high"
        rule_id, rule_name = "GOV-POST-001", rule("GOV-POST-001")["name"]
        finding_count = len(output_hits)
        context = "Governance finding GOV-POST-001: the previous tool output contained credential-shaped content. Do not reproduce it; use a managed secret reference."
        outcome = "finding_added_to_next_turn"
    elif hook_event == "Stop" and response_hits and rule_enabled(active_rules, "GOV-RESP-001"):
        decision, severity = "observed", "high"
        rule_id, rule_name = "GOV-RESP-001", rule("GOV-RESP-001")["name"]
        finding_count = len(response_hits)
        outcome = "response_finding_recorded"
    elif hook_event == "SessionStart":
        context = session_context()
        outcome = "managed_rules_added"

    # A deferred event reports the decision already made by the last-known-good
    # managed policy on the endpoint. It must remain historical evidence rather
    # than being re-evaluated under whatever policy happens to be active now.
    if deferred:
        decision = x_governance_local_decision if x_governance_local_decision in db.ALLOWED_DECISIONS else "observed"
        local_rule = safe_header(x_governance_local_rule, "") or None
        rule_id = local_rule if local_rule in RULES else None
        rule_name = RULES.get(rule_id or "", {}).get("name")
        severity = x_governance_local_severity if x_governance_local_severity in db.ALLOWED_SEVERITIES else (
            str(RULES.get(rule_id or "", {}).get("severity") or "info")
        )
        outcome = safe_header(x_governance_local_outcome, "offline_decision_recorded")
        reason = ""
        context = ""

    session = str(payload.get("session_id") or "")
    tool_use = str(payload.get("tool_use_id") or "")
    opaque_tool = opaque(tool_use) if tool_use else None
    tool_duration = None
    if not deferred and hook_event == "PreToolUse" and opaque_tool:
        db.start_tool(opaque_tool, now_ms)
    elif not deferred and hook_event == "PostToolUse" and opaque_tool:
        tool_duration = db.finish_tool(opaque_tool, now_ms)

    cwd = str(payload.get("cwd") or "")
    workspace = PurePath(cwd).name[:120] if cwd else "no-folder"
    secret_findings = sorted(set(prompt_hits + input_hits + output_hits + response_hits))
    detail = (
        f"Unapproved {package_ecosystem} package: {', '.join(unapproved_packages)}"
        if unapproved_packages and rule_id == "GOV-PKG-001"
        else f"Unmasked phone number in {tool_input_path(tool_input_raw) or 'file write'}"
        if rule_id == "GOV-PII-001"
        else f"Unsafe git command: {' '.join(git_reasons)}"
        if rule_id == "GOV-GIT-001"
        else f"Matched {', '.join(secret_findings)}" if finding_count
        else "Policy hook completed"
    )
    content_logged = int(bool(prompt_raw or tool_input_raw is not None or tool_output_raw is not None or response_raw))
    event = {
        "event_id": (
            x_governance_event_id.lower()
            if x_governance_event_id and re.fullmatch(r"[0-9a-fA-F-]{36}", x_governance_event_id)
            else str(uuid.uuid4())
        ),
        "occurred_at": safe_occurred_at(x_governance_occurred_at) if deferred else db.utcnow(),
        "user_name": safe_header(x_governance_user, "unknown user"),
        "device_name": safe_header(x_governance_device, "unknown device"),
        "device_id": safe_header(x_governance_device_id, "") or None,
        "organization": "Governance",
        "source": "mdm-enforced-hook",
        "delivery": "deferred" if deferred else "managed-hook",
        "profile_name": safe_header(x_governance_profile, "Bob Governance"),
        "profile_id": safe_header(x_governance_profile_id, "bob-governance"),
        "policy_version": (
            safe_header(x_governance_policy_version, active_policy_version())
            if deferred else active_policy_version()
        ),
        "bob_version": safe_header(x_bob_version, "2.1.0"),
        "bob_channel": safe_header(x_bob_channel, "insiders"),
        "hook_event": hook_event,
        "decision": decision,
        "rule_id": rule_id,
        "rule_name": rule_name,
        "severity": severity,
        "workspace": workspace,
        "tool_name": tool_name,
        "tool_category": "tool" if payload.get("tool_name") else None,
        "tool_use_id": opaque_tool,
        "outcome": outcome,
        "duration_ms": None if deferred else max(0, int((time.perf_counter_ns() - started) / 1_000_000)),
        "tool_duration_ms": tool_duration,
        "prompt_length_bucket": bucket(len(prompt_raw)) if hook_event == "UserPromptSubmit" else None,
        "response_length_bucket": bucket(len(response_raw)) if hook_event == "Stop" else None,
        "finding_count": finding_count,
        "hook_status": "complete",
        "content_logged": content_logged,
        "detail": detail,
        "evidence": (
            f"{len(phone_numbers)} unmasked phone number(s)" if rule_id == "GOV-PII-001"
            else ", ".join(unapproved_packages if rule_id == "GOV-PKG-001" else secret_findings) or None
        ),
        "prompt_content": prompt_text or None,
        "tool_input_content": tool_input_text or None,
        "tool_output_content": tool_output_text or None,
        "response_content": response_text or None,
        "session_id": opaque(session),
        "lab_ticket": lab_ticket(x_lab_ticket),
        "lab_role": lab_role(x_lab_role),
        "lab_branch": lab_branch(x_lab_branch),
        "lab_cost": lab_cost(x_lab_cost),
        "lab_tokens": lab_count(x_lab_tokens, 10**12),
        "lab_turns": lab_count(x_lab_turns, 1_000_000),
        "team": safe_header(x_governance_team, summaries.TEAM_DEFAULT),
        # Laptop-side round trip (network + server) of the previous governance call.
        "hook_rtt_prev_ms": lab_count(x_hook_prev_ms, 600_000),
        "lab_path": tool_input_path(tool_input_raw),
        "session_source": safe_header(str(payload.get("source") or ""), "")[:40] or None if hook_event == "SessionStart" else None,
    }
    # Governance check time: this server's own processing of the hook call,
    # measured for every call (a deferred event keeps duration_ms empty because
    # its decision was made on the endpoint).
    event["check_ms"] = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    if db.insert_event(clean_event(event, allow_content=True)):
        broker.publish(event_message(event))
    if db.storage_health().get("status") == "degraded":
        raise HTTPException(503, "Durable event storage is temporarily unavailable; retry is required.")
    return {"decision": decision, "reason": reason, "context": context, "event_id": event["event_id"]}


CONTENT_FIELDS = {"prompt_content", "tool_input_content", "tool_output_content", "response_content", "content_ref"}


def _scope(since: str | None, until: str | None, team: str | None, tz_offset: int | None) -> summaries.Scope:
    try:
        return summaries.Scope.parse(since, until, team, tz_offset or 0)
    except ValueError as exc:
        raise HTTPException(422, "since and until must be dates (YYYY-MM-DD), since first") from exc


def _audit_rows(filters: dict[str, Any], team: str | None, tz_offset: int | None, outcome: str | None = None) -> list[dict[str, Any]]:
    """Filtered events with `team` attached. With tz_offset, date bounds are the viewer's local days."""
    filters = dict(filters)
    if tz_offset is not None and (filters.get("since") or filters.get("until")):
        start, end = _scope(filters.get("since"), filters.get("until"), None, tz_offset).utc_bounds()
        filters["since"] = start
        filters["until"] = None
        rows = [row for row in db.filtered_events(filters) if not end or str(row.get("occurred_at") or "") < end]
    else:
        rows = db.filtered_events(filters)
    teams = summaries.team_map(db.all_events())
    for row in rows:
        row["team"] = teams.get(str(row.get("event_id")), summaries.TEAM_DEFAULT)
    rows = [row for row in rows if not team or row["team"] == team]
    if outcome:
        outcomes = summaries.tool_outcomes(db.all_events())
        rows = [row for row in rows if outcomes.get(str(row.get("event_id"))) == outcome]
    return rows


@app.get("/api/v1/events", dependencies=[Depends(require_dashboard)])
def events(
    user: str | None = None, device: str | None = None, profile: str | None = None,
    source: str | None = None, decision: str | None = None, rule: str | None = None,
    severity: str | None = None, event: str | None = None, tool: str | None = None,
    ticket: str | None = None, role: str | None = None, team: str | None = None, session: str | None = None,
    since: str | None = None, until: str | None = None, tz_offset: int | None = Query(None, ge=-840, le=840),
    q: str | None = None, limit: int = Query(250, ge=1, le=1000),
    sort: str = "time", direction: str = "desc",
    outcome: str | None = Query(None, pattern="^(completed|failed|blocked)$"),
) -> dict[str, Any]:
    filters = {
        "user": user, "device": device, "profile": profile, "source": source, "decision": decision, "rule": rule,
        "severity": severity, "event": event, "tool": tool, "ticket": ticket, "role": role,
        "session": session, "since": since, "until": until, "q": q,
    }
    rows = _audit_rows(filters, team, tz_offset, outcome)
    column = db.SORT_COLUMNS.get(sort, "occurred_at") if sort != "team" else "team"
    rows.sort(key=lambda row: (row.get(column) is not None, row.get(column) or ""), reverse=direction.lower() != "asc")
    rows = [{key: value for key, value in row.items() if key not in CONTENT_FIELDS} for row in rows[:limit]]
    return {"count": len(rows), "events": rows}


def _export_filters(user, ticket, event, decision, since, until, session=None) -> dict[str, Any]:
    return {"user": user, "ticket": ticket, "event": event, "decision": decision, "since": since, "until": until, "session": session}


@app.get("/api/v1/events.csv", dependencies=[Depends(require_dashboard)])
def events_csv(
    user: str | None = None, ticket: str | None = None, event: str | None = None,
    decision: str | None = None, since: str | None = None, until: str | None = None,
    team: str | None = None, session: str | None = None, tz_offset: int | None = Query(None, ge=-840, le=840),
    tool: str | None = None, rule: str | None = None, outcome: str | None = Query(None, pattern="^(completed|failed|blocked)$"),
) -> Response:
    """Audit log export: metadata columns only, detail redacted and masked, no content."""
    rows = _audit_rows({**_export_filters(user, ticket, event, decision, since, until, session), "tool": tool, "rule": rule}, team, tz_offset, outcome)
    buffer = io.StringIO()
    csv.writer(buffer).writerows(metrics.csv_rows(rows, redact))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return Response(
        buffer.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="governance-audit-{stamp}.csv"'},
    )


@app.get("/api/v1/events.jsonl", dependencies=[Depends(require_dashboard)])
def events_jsonl(
    user: str | None = None, ticket: str | None = None, event: str | None = None,
    decision: str | None = None, since: str | None = None, until: str | None = None,
    team: str | None = None, session: str | None = None, tz_offset: int | None = Query(None, ge=-840, le=840),
    tool: str | None = None, rule: str | None = None, outcome: str | None = Query(None, pattern="^(completed|failed|blocked)$"),
) -> Response:
    """Audit log export as JSON Lines: same columns and redaction as the CSV."""
    rows = _audit_rows({**_export_filters(user, ticket, event, decision, since, until, session), "tool": tool, "rule": rule}, team, tz_offset, outcome)
    body = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in metrics.export_records(rows, redact))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return Response(
        body, media_type="application/x-ndjson; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="governance-audit-{stamp}.jsonl"'},
    )


def _tool_run_ms(event: dict[str, Any]) -> float | None:
    """Tool run time for a PostToolUse: measured, else from the paired PreToolUse timestamp."""
    if event.get("hook_event") != "PostToolUse":
        return None
    if event.get("tool_duration_ms") is not None:
        return float(event["tool_duration_ms"])
    if not event.get("tool_use_id"):
        return None
    end = lab._parse(event.get("occurred_at"))
    starts = [
        lab._parse(row.get("occurred_at")) for row in db.all_events()
        if row.get("hook_event") == "PreToolUse" and row.get("tool_use_id") == event["tool_use_id"]
    ]
    starts = [start for start in starts if start and end and start <= end]
    return round((end - max(starts)).total_seconds() * 1000, 1) if starts else None


@app.get("/api/v1/events/{event_id}", dependencies=[Depends(require_dashboard)])
def event_detail(event_id: str, tz_offset: int = Query(0, ge=-840, le=840)) -> dict[str, Any]:
    """One event, hydrated and redacted, plus a plain-language view for the drawer.

    Fields without a value are left out of both.
    """
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", event_id):
        raise HTTPException(404, "event not found")
    event = db.get_event(event_id.lower())
    if not event:
        raise HTTPException(404, "event not found")
    check = event.get("duration_ms") if event.get("duration_ms") is not None else event.get("check_ms")
    event["check_ms"] = check
    event["tool_run_ms"] = _tool_run_ms(event)
    event["team"] = summaries.team_map(db.all_events()).get(str(event.get("event_id")), event.get("team"))
    cleaned = {key: value for key, value in event.items() if value not in (None, "", [], {})}
    return {"event": cleaned, "view": detail.build(cleaned, RULES.get(str(cleaned.get("rule_id") or "")), tz_offset, redact)}


@app.get("/api/v1/facets", dependencies=[Depends(require_dashboard)])
def facets() -> dict[str, list[str]]:
    result = db.facets()
    result["teams"] = sorted(set(summaries.team_map(db.all_events()).values()))
    return result


@app.get("/api/v1/summary", dependencies=[Depends(require_dashboard)])
def summary() -> dict[str, Any]:
    return db.summary()


@app.get("/api/v1/analytics", dependencies=[Depends(require_dashboard)])
def analytics(
    days: int = Query(30, ge=1, le=90),
    granularity: str = Query("auto", pattern="^(auto|hour|day)$"),
) -> dict[str, Any]:
    return db.analytics(days=days, granularity=granularity)


@app.get("/api/v1/fleet", dependencies=[Depends(require_dashboard)])
def fleet() -> dict[str, Any]:
    rows = db.fleet()
    return {"count": len(rows), "devices": rows}


@app.get("/api/v1/policies", dependencies=[Depends(require_dashboard)])
def policies() -> dict[str, Any]:
    active = db.active_policy()
    return {
        "policy_version": (active or {}).get("version", POLICY_VERSION),
        "status": "active",
        "config": (active or {}).get("config", default_policy_config()),
        "rules": [{"rule_id": rule_id, **definition} for rule_id, definition in RULES.items()],
    }


class PolicyDraftUpdate(BaseModel):
    expected_revision: str = Field(min_length=1, max_length=40)
    config: dict[str, Any]


class PolicyPublishRequest(BaseModel):
    expected_revision: str = Field(min_length=1, max_length=40)


def validate_policy_config(config: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if config.get("name") != "Bob Governance":
        errors.append({"path": "name", "message": "Policy name must remain Bob Governance."})
    entries = config.get("rules")
    if not isinstance(entries, list):
        return errors + [{"path": "rules", "message": "Rules must be a list."}]
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"rules[{index}]"
        if not isinstance(entry, dict):
            errors.append({"path": path, "message": "Rule must be an object."})
            continue
        rule_id = str(entry.get("rule_id") or "")
        if rule_id not in RULES:
            errors.append({"path": f"{path}.rule_id", "message": "Unknown rule identifier."})
        if rule_id in seen:
            errors.append({"path": f"{path}.rule_id", "message": "Rule appears more than once."})
        seen.add(rule_id)
        if not isinstance(entry.get("enabled"), bool):
            errors.append({"path": f"{path}.enabled", "message": "Enabled must be true or false."})
        if rule_id == "GOV-PKG-001":
            allowlist = entry.get("configuration", {}).get("allowlist")
            if not isinstance(allowlist, dict):
                errors.append({"path": f"{path}.configuration.allowlist", "message": "Package allowlist is required."})
            else:
                for ecosystem in ("python", "node"):
                    packages = allowlist.get(ecosystem)
                    if not isinstance(packages, list) or not all(
                        isinstance(package, str) and re.fullmatch(r"@?[a-z0-9][a-z0-9._/-]*", package)
                        for package in packages
                    ):
                        errors.append({
                            "path": f"{path}.configuration.allowlist.{ecosystem}",
                            "message": "Use a list of normalized package names.",
                        })
    missing = sorted(set(RULES) - seen)
    if missing:
        errors.append({"path": "rules", "message": f"Missing managed rules: {', '.join(missing)}."})
    offline = config.get("offline", {})
    if offline.get("enforcement") != "last_known_good":
        errors.append({"path": "offline.enforcement", "message": "Offline enforcement must use the last verified policy."})
    if offline.get("missing_policy_behavior") not in {"fail_open", "fail_closed"}:
        errors.append({"path": "offline.missing_policy_behavior", "message": "Choose fail_open or fail_closed."})
    for key, maximum in (("queue_max_events", 5000), ("queue_max_bytes", 104_857_600), ("retry_max_seconds", 3600)):
        value = offline.get(key)
        if not isinstance(value, int) or value < 1 or value > maximum:
            errors.append({"path": f"offline.{key}", "message": f"Enter a value from 1 to {maximum}."})
    return errors


def next_policy_version(current: str) -> str:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", current)
    if not match:
        return datetime.now(timezone.utc).strftime("%Y.%m.%d%H%M%S")
    major, minor, patch = (int(part) for part in match.groups())
    return f"{major}.{minor}.{patch + 1}"


def serialize_policy_draft(draft: dict[str, Any] | None) -> dict[str, Any]:
    active = db.active_policy()
    if not draft:
        return {}
    configured = {
        str(entry.get("rule_id")): entry
        for entry in draft.get("config", {}).get("rules", [])
        if isinstance(entry, dict)
    }
    rules = []
    for rule_id, definition in RULES.items():
        entry = configured.get(rule_id, {})
        merged = {"rule_id": rule_id, **definition, "enabled": entry.get("enabled", True)}
        if "configuration" in entry:
            merged["configuration"] = entry["configuration"]
        rules.append(merged)
    return {
        "policy_version": (active or {}).get("version", POLICY_VERSION),
        "revision": draft["revision"],
        "status": draft["status"],
        "updated_at": draft.get("updated_at"),
        "updated_by": draft.get("created_by"),
        "rules": rules,
        "offline": draft.get("config", {}).get("offline", {}),
        "content": draft.get("config", {}).get("content", {}),
    }


@app.get("/api/v1/policy/draft")
def get_policy_draft(actor: str = Depends(require_dashboard)) -> dict[str, Any]:
    del actor
    return serialize_policy_draft(db.draft_policy())


@app.put("/api/v1/policy/draft")
def put_policy_draft(body: PolicyDraftUpdate, actor: str = Depends(require_dashboard)) -> dict[str, Any]:
    errors = validate_policy_config(body.config)
    if errors:
        raise HTTPException(422, detail={"valid": False, "errors": errors})
    try:
        return serialize_policy_draft(db.save_policy_draft(body.config, body.expected_revision, actor))
    except ValueError as exc:
        raise HTTPException(409, "The draft changed. Reload it before saving again.") from exc
    except ObjectStoreUnavailable as exc:
        raise HTTPException(503, "The policy store is temporarily unavailable. No draft change was committed.") from exc


@app.post("/api/v1/policy/validate")
def validate_policy(body: PolicyDraftUpdate, actor: str = Depends(require_dashboard)) -> dict[str, Any]:
    del actor
    errors = validate_policy_config(body.config)
    return {"valid": not errors, "errors": errors}


@app.post("/api/v1/policy/publish")
def publish_policy(
    body: PolicyPublishRequest,
    request: Request,
    actor: str = Depends(require_dashboard),
) -> dict[str, Any]:
    draft = db.draft_policy()
    if not draft or draft["revision"] != body.expected_revision:
        raise HTTPException(409, "The draft changed. Reload it before publishing.")
    errors = validate_policy_config(draft["config"])
    if errors:
        raise HTTPException(422, detail={"valid": False, "errors": errors})
    active = db.active_policy() or {"version": POLICY_VERSION}
    version = next_policy_version(str(active["version"]))
    try:
        candidate, rollout_id = db.publish_policy_draft(version, actor)
    except ObjectStoreUnavailable as exc:
        raise HTTPException(503, "The policy release could not be staged durably. Nothing was published.") from exc
    if lab_mode():
        # Lab mode: no MDM. The staged release becomes the active policy in the
        # object store, and hook decisions use it at once.
        try:
            published = db.finalize_policy_publication(rollout_id, target_count=0)
        except ObjectStoreUnavailable as exc:
            raise HTTPException(503, "The policy release could not be finalized durably. The current active policy was not changed.") from exc
        return {"ok": True, "policy": published, "rollout": db.latest_rollout(), "rollout_id": rollout_id, "mode": "lab"}
    public_url = (os.environ.get("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")
    try:
        profile = build_profile(
            config=candidate["config"],
            version=version,
            api_url=public_url,
            ingest_token=ingest_token(),
            profile_id=os.environ.get("SIMPLEMDM_PROFILE_ID", "100001"),
        )
        result = mdm.publish_profile(profile)
        published = db.finalize_policy_publication(
            rollout_id, target_count=int(result.get("target_count", 0))
        )
    except mdm.MDMNotConfigured as exc:
        try:
            db.update_rollout(rollout_id, "configuration_required", error=str(exc))
        except ObjectStoreUnavailable:
            pass
        raise HTTPException(503, "Managed policy delivery is not configured. The current active policy was not changed.") from exc
    except ObjectStoreUnavailable as exc:
        raise HTTPException(503, "The policy release could not be finalized durably. The current active policy was not changed.") from exc
    except Exception as exc:
        try:
            db.update_rollout(rollout_id, "failed", error=str(exc)[:512])
        except ObjectStoreUnavailable:
            pass
        raise HTTPException(502, "Managed policy delivery failed. The current active policy was not changed.") from exc
    return {"ok": True, "policy": published, "rollout": db.latest_rollout(), "rollout_id": rollout_id}


@app.get("/api/v1/rollouts/latest")
def rollout_latest(actor: str = Depends(require_dashboard)) -> dict[str, Any]:
    del actor
    return {"rollout": db.latest_rollout()}


def lab_mode() -> bool:
    return (os.environ.get("LAB_MODE") or "").strip().lower() in {"1", "true", "yes"}


CI_VERDICTS = {"PASS", "FAIL"}


class LabEvent(BaseModel):
    kind: str = Field(pattern="^(pr_opened|ci_result|approved|merged|ticket_started|ticket_done)$")
    user: str = Field(min_length=1, max_length=120)
    ticket: str = Field(min_length=1, max_length=20)
    pr: int | None = Field(default=None, ge=0, le=10_000_000)
    data: dict[str, Any] = Field(default_factory=dict)
    role: str | None = None
    branch: str | None = None
    cost: float | None = None
    occurred_at: str | None = None
    event_id: str | None = None


def _lab_number(data: dict[str, Any], key: str, kind: type) -> Any:
    value = data.get(key)
    if value is None:
        return None
    try:
        number = kind(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, f"data.{key} must be a number") from exc
    if number < 0:
        raise HTTPException(422, f"data.{key} must not be negative")
    return number


def _lab_text(value: Any, limit: int = 200) -> str | None:
    if value is None:
        return None
    text = mask_stored(redact(str(value))[0]).strip()[:limit]
    if not SAFE_TEXT.match(text):
        raise HTTPException(422, "invalid text in lab event data")
    return text or None


def _lab_url(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::\d+)?(?:/[A-Za-z0-9._~%/+#?&=:-]*)?", text) or len(text) > 400:
        raise HTTPException(422, "URLs must be https links")
    return text


def _lab_lines(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise HTTPException(422, "findings_list must be a list of strings")
    return [line for line in (_lab_text(item) for item in value[:20]) if line]


def clean_lab_data(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the data object of a lab event. Values stay short and scalar."""
    reject_sensitive_shape(data)
    if len(json.dumps(data)) > 4096:
        raise HTTPException(413, "lab event data is too large")
    if kind == "ci_result":
        verdict = str(data.get("verdict") or "").upper()
        if verdict not in CI_VERDICTS:
            raise HTTPException(422, "data.verdict must be PASS or FAIL")
        return {
            "tests_passed": _lab_number(data, "tests_passed", int),
            "tests_total": _lab_number(data, "tests_total", int),
            "verdict": verdict,
            "findings": _lab_number(data, "findings", int),
            "blocking": _lab_number(data, "blocking", int),
            "seconds": _lab_number(data, "seconds", float),
            "criteria_met": _lab_number(data, "criteria_met", int),
            "criteria_total": _lab_number(data, "criteria_total", int),
            "findings_list": _lab_lines(data.get("findings_list")),
            "pr_url": _lab_url(data.get("pr_url")),
            "run_url": _lab_url(data.get("run_url")),
        }
    if kind == "merged":
        approver = data.get("approver")
        return {
            "approver": safe_header(str(approver), "") or None if approver is not None else None,
            "review_rounds": _lab_number(data, "review_rounds", int),
            "lines_changed": _lab_number(data, "lines_changed", int),
            "title": _lab_text(data.get("title")),
            "pr_url": _lab_url(data.get("pr_url")),
        }
    cleaned: dict[str, Any] = {}
    for key, value in list(data.items())[:20]:
        name = re.sub(r"[^A-Za-z0-9_]", "", str(key))[:40]
        if not name:
            continue
        if name == "pr_url":
            cleaned[name] = _lab_url(value)
        elif name == "title":
            cleaned[name] = _lab_text(value)
        elif isinstance(value, (bool, int, float)) or value is None:
            cleaned[name] = value
        else:
            text = str(value)
            if not SAFE_TEXT.match(text):
                raise HTTPException(422, f"invalid text in data.{name}")
            cleaned[name] = text[:256]
    return cleaned


@app.post("/api/v1/lab/events", dependencies=[Depends(require_ingest)])
def ingest_lab_event(body: LabEvent) -> dict[str, Any]:
    """Record a lab event that happens outside Bob (GitHub, CI)."""
    ticket = lab_ticket(body.ticket)
    if not ticket:
        raise HTTPException(422, "ticket must look like KAN-201")
    data = clean_lab_data(body.kind, body.data)
    default_role = "ci-reviewer" if body.kind == "ci_result" else None
    detail = f"{body.kind.replace('_', ' ')} for {ticket}" + (f" (PR #{body.pr})" if body.pr is not None else "")
    if body.kind == "ci_result":
        detail += f": {data['verdict']}, {data.get('findings') or 0} findings"
    event_id = (
        body.event_id.lower()
        if body.event_id and re.fullmatch(r"[0-9a-fA-F-]{36}", body.event_id)
        else str(uuid.uuid4())
    )
    event = {
        "event_id": event_id,
        "occurred_at": safe_occurred_at(body.occurred_at),
        "user_name": safe_header(body.user, "unknown user"),
        "device_name": "ci" if body.kind == "ci_result" else "github",
        "device_id": None,
        "organization": "Governance",
        "source": "lab",
        "delivery": "lab-event",
        "profile_name": "Bob SDLC Lab",
        "profile_id": "bob-sdlc-lab",
        "policy_version": active_policy_version(),
        "hook_event": f"lab.{body.kind}",
        "decision": "allowed",
        "severity": "info",
        "outcome": body.kind,
        "detail": detail,
        "finding_count": int(data.get("findings") or 0) if body.kind == "ci_result" else 0,
        "lab_ticket": ticket,
        "lab_role": lab_role(body.role) or default_role,
        "lab_branch": lab_branch(body.branch),
        "lab_cost": lab_cost(None if body.cost is None else str(body.cost)),
        "lab_kind": body.kind,
        "lab_pr": body.pr,
        "lab_data": data,
    }
    inserted = db.insert_event(clean_event(event, allow_content=True))
    if inserted:
        broker.publish(event_message(event))
    return {"ok": True, "event_id": event_id, "inserted": inserted}


@app.get("/api/v1/lab/board", dependencies=[Depends(require_dashboard)])
def lab_board() -> dict[str, Any]:
    rows = lab.lab_board(db.all_events())
    return {"count": len(rows), "tickets": rows}


@app.get("/api/v1/lab/roi", dependencies=[Depends(require_dashboard)])
def lab_roi(baseline_minutes: float = Query(240, gt=0, le=100_000)) -> dict[str, Any]:
    return lab.lab_roi(db.all_events(), baseline_minutes=baseline_minutes)


def _summary_scope(
    since: str | None = None, until: str | None = None, team: str | None = None,
    tz_offset: int = Query(0, ge=-840, le=840),
) -> summaries.Scope:
    return _scope(since, until, team, tz_offset)


@app.get("/api/v1/overview/summary", dependencies=[Depends(require_dashboard)])
def overview_summary(scope: summaries.Scope = Depends(_summary_scope)) -> dict[str, Any]:
    return summaries.overview(db.all_events(), scope)


@app.get("/api/v1/cost/summary", dependencies=[Depends(require_dashboard)])
def cost_summary(scope: summaries.Scope = Depends(_summary_scope)) -> dict[str, Any]:
    return summaries.cost(db.all_events(), scope)


@app.get("/api/v1/delivery/summary", dependencies=[Depends(require_dashboard)])
def delivery_summary(scope: summaries.Scope = Depends(_summary_scope)) -> dict[str, Any]:
    return summaries.delivery(db.all_events(), scope)


@app.get("/api/v1/performance/summary", dependencies=[Depends(require_dashboard)])
def performance_summary(scope: summaries.Scope = Depends(_summary_scope)) -> dict[str, Any]:
    return summaries.performance(db.all_events(), scope)


@app.get("/api/v1/violations/summary", dependencies=[Depends(require_dashboard)])
def violations_summary(
    scope: summaries.Scope = Depends(_summary_scope), limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    return summaries.violations(db.all_events(), scope, redact, limit=limit)


@app.get("/api/v1/sessions/{session_id}", dependencies=[Depends(require_dashboard)])
def session_detail(session_id: str, tz_offset: int = Query(0, ge=-840, le=840)) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session_id):
        raise HTTPException(404, "session not found")
    result = summaries.session_summary(db.all_events(), session_id, tz_offset)
    if not result:
        raise HTTPException(404, "session not found")
    return result


@app.get("/api/v1/rules/summary", dependencies=[Depends(require_dashboard)])
def rules_summary(scope: summaries.Scope = Depends(_summary_scope)) -> dict[str, Any]:
    enabled = {rule_id: bool(entry.get("enabled", True)) for rule_id, entry in runtime_rules().items()}
    return summaries.rules(db.all_events(), scope, RULES, enabled)


@app.get("/api/v1/stream", dependencies=[Depends(require_dashboard)])
async def stream(request: Request, once: bool = False) -> StreamingResponse:
    """Server-Sent Events: one `data:` line per ingested event, a heartbeat comment every 15 s.

    `once=1` sends the recent backlog and closes (used by tests and health checks).
    """
    async def events():
        yield "retry: 5000\n\n"
        if once:
            for message in list(broker.recent):
                yield f"data: {json.dumps(message)}\n\n"
            return
        entry = broker.subscribe()
        try:
            while not await request.is_disconnected():
                try:
                    message = await asyncio.wait_for(entry[1].get(), timeout=HEARTBEAT_SECONDS)
                    yield f"data: {json.dumps(message)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            broker.unsubscribe(entry)

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive",
    })
