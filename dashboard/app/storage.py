from __future__ import annotations

import json
import os
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class ObjectConflict(RuntimeError):
    """Raised when an immutable object key is reused with different content."""


class ObjectStoreUnavailable(RuntimeError):
    """Raised when neither the object store nor the bounded retry queue can accept a write."""


class ObjectRepository(Protocol):
    mode: str

    def put_json(self, key: str, value: dict[str, Any], *, immutable: bool = False) -> None: ...
    def get_json(self, key: str) -> dict[str, Any] | None: ...
    def list_json(self, prefix: str) -> list[tuple[str, dict[str, Any]]]: ...


def _encoded(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


class LocalObjectRepository:
    """Filesystem object store used only for development and isolated tests."""

    mode = "local"

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("invalid object key")
        return path

    def put_json(self, key: str, value: dict[str, Any], *, immutable: bool = False) -> None:
        path = self._path(key)
        body = _encoded(value)
        if immutable and path.exists():
            if path.read_bytes() != body:
                raise ObjectConflict(f"immutable object already exists: {key}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        temporary.write_bytes(body)
        os.replace(temporary, path)

    def get_json(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_json(self, prefix: str) -> list[tuple[str, dict[str, Any]]]:
        base = self._path(prefix)
        if not base.exists():
            return []
        paths = [base] if base.is_file() else sorted(base.rglob("*.json"))
        return [
            (str(path.relative_to(self.root)), json.loads(path.read_text(encoding="utf-8")))
            for path in paths
        ]


def _binding_credentials() -> dict[str, Any]:
    """Extract a COS credential object from standard IBM service-binding JSON."""
    for variable in ("CE_SERVICES", "VCAP_SERVICES"):
        raw = os.environ.get(variable)
        if not raw:
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        stack: list[Any] = [value]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if item.get("apikey") and item.get("resource_instance_id"):
                    return item
                credentials = item.get("credentials")
                if isinstance(credentials, dict) and (
                    credentials.get("apikey") or credentials.get("cos_hmac_keys")
                ):
                    return credentials
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
    return {}


class COSObjectRepository:
    """IBM Cloud Object Storage repository using its S3-compatible SDK."""

    mode = "cos"

    def __init__(self) -> None:
        try:
            import ibm_boto3
            from ibm_botocore.client import Config
        except ImportError as exc:  # pragma: no cover - exercised in deployment
            raise ObjectStoreUnavailable("IBM COS SDK is not installed") from exc

        credentials = _binding_credentials()
        self.bucket = (os.environ.get("COS_BUCKET") or os.environ.get("IBM_COS_BUCKET") or "").strip()
        self.endpoint = (os.environ.get("COS_ENDPOINT") or os.environ.get("IBM_COS_ENDPOINT") or "").strip()
        if not self.bucket or not self.endpoint:
            raise ObjectStoreUnavailable("COS_BUCKET and COS_ENDPOINT are required")

        api_key = (
            os.environ.get("COS_API_KEY")
            or os.environ.get("IBM_COS_APIKEY")
            or credentials.get("apikey")
        )
        instance_id = (
            os.environ.get("COS_RESOURCE_INSTANCE_ID")
            or os.environ.get("IBM_COS_RESOURCE_INSTANCE_ID")
            or credentials.get("resource_instance_id")
        )
        hmac = credentials.get("cos_hmac_keys") if isinstance(credentials.get("cos_hmac_keys"), dict) else {}
        access_key = os.environ.get("COS_ACCESS_KEY_ID") or hmac.get("access_key_id")
        secret_key = os.environ.get("COS_SECRET_ACCESS_KEY") or hmac.get("secret_access_key")
        if api_key and instance_id:
            self.client = ibm_boto3.client(
                "s3",
                ibm_api_key_id=api_key,
                ibm_service_instance_id=instance_id,
                ibm_auth_endpoint="https://iam.cloud.ibm.com/identity/token",
                config=Config(signature_version="oauth", connect_timeout=5, read_timeout=15, retries={"max_attempts": 3}),
                endpoint_url=self.endpoint,
            )
        elif access_key and secret_key:
            self.client = ibm_boto3.client(
                "s3",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=15, retries={"max_attempts": 3}),
                endpoint_url=self.endpoint,
            )
        else:
            raise ObjectStoreUnavailable("COS service binding or HMAC credentials are required")

    def put_json(self, key: str, value: dict[str, Any], *, immutable: bool = False) -> None:
        body = _encoded(value)
        if immutable:
            current = self.get_json(key)
            if current is not None:
                if _encoded(current) != body:
                    raise ObjectConflict(f"immutable object already exists: {key}")
                return
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            CacheControl="no-store",
        )

    def get_json(self, key: str) -> dict[str, Any] | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # the SDK exception hierarchy is generated dynamically
            code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
            if code in {"NoSuchKey", "404", "NotFound"}:
                return None
            raise
        return json.loads(response["Body"].read().decode("utf-8"))

    def list_json(self, prefix: str) -> list[tuple[str, dict[str, Any]]]:
        result: list[tuple[str, dict[str, Any]]] = []
        token: str | None = None
        while True:
            request: dict[str, Any] = {"Bucket": self.bucket, "Prefix": prefix, "MaxKeys": 1000}
            if token:
                request["ContinuationToken"] = token
            page = self.client.list_objects_v2(**request)
            for item in page.get("Contents", []):
                key = str(item["Key"])
                value = self.get_json(key)
                if value is not None:
                    result.append((key, value))
            if not page.get("IsTruncated"):
                break
            token = page.get("NextContinuationToken")
        return result


class ResilientObjectRepository:
    """Bounded in-memory retry queue that keeps hook ingestion responsive during brief outages."""

    def __init__(self, delegate: ObjectRepository, *, prefix: str, queue_limit: int) -> None:
        self.delegate = delegate
        self.mode = delegate.mode
        self.prefix = prefix.strip("/")
        self.queue_limit = max(1, min(queue_limit, 50_000))
        self._pending: deque[tuple[str, dict[str, Any], bool]] = deque()
        self._lock = threading.RLock()
        self._last_success: str | None = None
        self._last_error_at: str | None = None
        self._last_error_type: str | None = None

    def _key(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def _mark_success(self) -> None:
        self._last_success = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if not self._pending:
            self._last_error_type = None

    def _mark_error(self, exc: Exception) -> None:
        self._last_error_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._last_error_type = type(exc).__name__

    def flush_pending(self, limit: int = 100) -> int:
        flushed = 0
        with self._lock:
            while self._pending and flushed < limit:
                key, value, immutable = self._pending[0]
                try:
                    self.delegate.put_json(self._key(key), value, immutable=immutable)
                except Exception as exc:
                    self._mark_error(exc)
                    break
                self._pending.popleft()
                flushed += 1
                self._mark_success()
        return flushed

    def put_json(self, key: str, value: dict[str, Any], *, immutable: bool = False) -> None:
        with self._lock:
            self.flush_pending(limit=25)
            if self._pending:
                if len(self._pending) >= self.queue_limit:
                    raise ObjectStoreUnavailable("object-store retry queue is full")
                self._pending.append((key, value, immutable))
                return
            try:
                self.delegate.put_json(self._key(key), value, immutable=immutable)
                self._mark_success()
                return
            except ObjectConflict:
                raise
            except Exception as exc:
                self._mark_error(exc)
                if len(self._pending) >= self.queue_limit:
                    raise ObjectStoreUnavailable("object-store retry queue is full") from exc
                self._pending.append((key, value, immutable))

    def put_json_durable(self, key: str, value: dict[str, Any], *, immutable: bool = False) -> None:
        """Write through to the durable delegate without accepting an in-memory queue result.

        Governance control-plane callers use this method when returning success would
        cause an operator to believe a draft, release, pointer, or rollout transition
        survived a process restart. Pending event writes do not prevent a direct
        control-plane attempt; the two paths intentionally have different guarantees.
        """
        with self._lock:
            try:
                self.delegate.put_json(self._key(key), value, immutable=immutable)
                self._mark_success()
            except ObjectConflict:
                raise
            except Exception as exc:
                self._mark_error(exc)
                raise ObjectStoreUnavailable("durable object-store write failed") from exc

    def get_json_durable(self, key: str) -> dict[str, Any] | None:
        """Read only the durable delegate, ignoring queued data-plane writes."""
        try:
            value = self.delegate.get_json(self._key(key))
            self._mark_success()
            return value
        except Exception as exc:
            self._mark_error(exc)
            raise ObjectStoreUnavailable("durable object-store read failed") from exc

    def get_json(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            for pending_key, pending_value, _ in reversed(self._pending):
                if pending_key == key:
                    return dict(pending_value)
        try:
            value = self.delegate.get_json(self._key(key))
            self._mark_success()
            return value
        except Exception as exc:
            self._mark_error(exc)
            raise ObjectStoreUnavailable("object store read failed") from exc

    def list_json(self, prefix: str) -> list[tuple[str, dict[str, Any]]]:
        try:
            stored = self.delegate.list_json(self._key(prefix))
            root = f"{self.prefix}/" if self.prefix else ""
            values = {key.removeprefix(root): value for key, value in stored}
            self._mark_success()
        except Exception as exc:
            self._mark_error(exc)
            values = {}
        with self._lock:
            for key, value, _ in self._pending:
                if key.startswith(prefix):
                    values[key] = dict(value)
        return sorted(values.items())

    def health(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "status": "degraded" if self._pending or self._last_error_type else "available",
            "pending_writes": len(self._pending),
            "queue_limit": self.queue_limit,
            "last_success_at": self._last_success,
            "last_error_at": self._last_error_at,
            "last_error_type": self._last_error_type,
        }


def build_repository() -> ResilientObjectRepository:
    has_cos_bucket = os.environ.get("COS_BUCKET") or os.environ.get("IBM_COS_BUCKET")
    mode = (os.environ.get("OBJECT_STORE_MODE") or ("cos" if has_cos_bucket else "local")).lower()
    if mode == "cos":
        delegate: ObjectRepository = COSObjectRepository()
    elif mode == "local":
        root = os.environ.get("OBJECT_STORE_DIR") or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")), "objects"
        )
        delegate = LocalObjectRepository(root)
    else:
        raise ValueError("OBJECT_STORE_MODE must be 'cos' or 'local'")
    return ResilientObjectRepository(
        delegate,
        prefix=os.environ.get("COS_PREFIX", "bob-governance/v1"),
        queue_limit=int(os.environ.get("OBJECT_STORE_QUEUE_MAX", "2000")),
    )
