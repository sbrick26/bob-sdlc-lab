"""In-memory fan-out of ingested events to Server-Sent Events subscribers.

The app runs as one instance, so a process-local broker is enough. Ingest code
may run in a worker thread; publish() hands each message to the subscriber's
event loop thread-safely and drops it when that subscriber is too far behind.
"""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from typing import Any

HEARTBEAT_SECONDS = 15
QUEUE_SIZE = 200


class Broker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()
        self.recent: deque[dict[str, Any]] = deque(maxlen=50)

    def subscribe(self) -> tuple[asyncio.AbstractEventLoop, asyncio.Queue]:
        entry = (asyncio.get_running_loop(), asyncio.Queue(maxsize=QUEUE_SIZE))
        with self._lock:
            self._subscribers.add(entry)
        return entry

    def unsubscribe(self, entry: tuple[asyncio.AbstractEventLoop, asyncio.Queue]) -> None:
        with self._lock:
            self._subscribers.discard(entry)

    def publish(self, message: dict[str, Any]) -> None:
        self.recent.append(message)
        with self._lock:
            subscribers = list(self._subscribers)
        for loop, queue in subscribers:
            try:
                loop.call_soon_threadsafe(_offer, queue, message)
            except RuntimeError:
                self.unsubscribe((loop, queue))


def _offer(queue: asyncio.Queue, message: dict[str, Any]) -> None:
    try:
        queue.put_nowait(message)
    except asyncio.QueueFull:
        pass


broker = Broker()


def event_message(event: dict[str, Any]) -> dict[str, Any]:
    """The small payload sent to the browser; no content, only identifiers."""
    return {
        "type": event.get("lab_kind") or event.get("hook_event"),
        "event_id": event.get("event_id"),
        "user": event.get("user_name"),
        "ticket": event.get("lab_ticket"),
        "decision": event.get("decision"),
    }
