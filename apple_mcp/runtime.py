"""Native-call runtime: serialize ALL EventKit access onto ONE dedicated thread.

Settled by design (adversarial debate). ``EKEventStore`` has **thread affinity** (it
must be accessed from the thread that created it) and **TCC** authorization must be
handled on a consistent thread. A generic ``asyncio.to_thread`` / default multi-worker
pool scatters calls across threads → affinity bugs and a hung first-permission prompt.
So every native call goes through a single ``max_workers=1`` executor; the
``EKEventStore``
itself is created *inside* that worker, lazily by ``store()`` (owned by runtime, not the
adapters — they obtain it by calling ``store()`` via run_native).

This is user-latency-bound, not throughput-bound, so serialization costs nothing in
practice.
"""

from __future__ import annotations

import logging
import subprocess
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import TypeVar

import EventKit as EK
import Foundation as F

T = TypeVar("T")

# ponytail: one process-wide native thread. If a future app needs a *second* isolated
# native context, give it its own executor — don't widen this one to max_workers>1
# (breaks EKEventStore).
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="apple-native")


def run_native(fn: Callable[[], T]) -> T:
    """Run a blocking native callable on the single dedicated worker thread and return
    its result.

    Adapters wrap every EventKit / osascript call in this so the work always lands on
    one thread, regardless of which thread FastMCP invoked the tool from.
    """
    return _executor.submit(fn).result()


_FULL_ACCESS = EK.EKAuthorizationStatusFullAccess  # == 3 on macOS 14+

# Generous (this wait blocks on the user answering a TCC prompt) but bounded: a callback
# that never fires (headless/sandboxed, EventKit error) must not hang the sole worker —
# and every later run_native — forever. ponytail: bump if a user legitimately needs
# >2min to click Allow.
_ACCESS_TIMEOUT = 120.0  # seconds


class AccessDenied(RuntimeError):
    """Raised when Calendar/Reminders TCC access is not fully granted."""


def _decide(status: int) -> None:
    """Map an EKAuthorizationStatus to a decision: return on full access, else raise."""
    if status == _FULL_ACCESS:
        return
    raise AccessDenied(
        "apple-mcp needs Calendar + Reminders access. Grant it in "
        "System Settings → Privacy & Security → Calendars and Reminders, then "
        "restart apple-mcp."
    )


_store: EK.EKEventStore | None = None


def _on_worker() -> bool:
    return threading.current_thread().name.startswith("apple-native")


def store() -> EK.EKEventStore:
    """The one process-wide EKEventStore, created lazily on the worker thread.

    Owned by runtime (not an adapter) so both adapters share one store without reaching
    into each other. Must be called from inside run_native (the apple-native worker).
    """
    global _store
    if not _on_worker():
        raise RuntimeError(
            "store() must be called on the apple-native worker — wrap the call in "
            "run_native()"
        )
    if _store is None:
        _store = EK.EKEventStore.alloc().init()
    return _store


# osascript is the escape hatch for apps with no PyObjC framework (Mail, Notes, etc.).
# It runs on the SAME worker as EventKit — serialized, never concurrent — so the
# max_workers=1 fence covers all native access. A timeout bounds it so a hung script
# (e.g. a modal permission dialog) can't block the worker forever.
_OSASCRIPT_TIMEOUT = 30.0  # seconds


def run_osascript(script: str, timeout: float = _OSASCRIPT_TIMEOUT) -> str:
    """Run an AppleScript via ``osascript`` on the native worker; return stdout.

    The sanctioned escape hatch for framework-less apps (Mail/Notes/Music/Safari).
    Raises RuntimeError on a non-zero exit (app not running, TCC denied, script error)
    or timeout — it never returns an empty string to mask a failure as "no result".
    Safe on or off the worker (dispatches via run_native when called off it).
    """

    def _run() -> str:
        try:
            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"osascript timed out after {timeout}s") from e
        if proc.returncode != 0:
            raise RuntimeError(f"osascript failed: {proc.stderr.strip()}")
        return proc.stdout.rstrip("\n")

    return _run() if _on_worker() else run_native(_run)


def to_nsdate(dt: datetime) -> F.NSDate:
    return F.NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def from_nsdate(d: F.NSDate) -> datetime:
    return datetime.fromtimestamp(d.timeIntervalSince1970())


def due_components(dt: datetime) -> F.NSDateComponents:
    c = F.NSDateComponents.alloc().init()
    c.setYear_(dt.year)
    c.setMonth_(dt.month)
    c.setDay_(dt.day)
    c.setHour_(dt.hour)
    c.setMinute_(dt.minute)
    return c


log = logging.getLogger("apple_mcp")


def _request_one(s: EK.EKEventStore, entity: int) -> None:
    """Request access for one entity type if undetermined, blocking on the async
    callback."""
    status = EK.EKEventStore.authorizationStatusForEntityType_(entity)
    if status == EK.EKAuthorizationStatusNotDetermined:
        done = threading.Event()
        requester = (
            s.requestFullAccessToEventsWithCompletion_
            if entity == EK.EKEntityTypeEvent
            else s.requestFullAccessToRemindersWithCompletion_
        )

        def handler(granted, error, _done=done):  # fires on a GCD queue, not our worker
            _done.set()

        requester(handler)
        if not done.wait(timeout=_ACCESS_TIMEOUT):
            raise AccessDenied(
                "Timed out waiting for the Calendar/Reminders permission response."
            )
        status = EK.EKEventStore.authorizationStatusForEntityType_(entity)
    _decide(status)


def request_access() -> None:
    """Ensure full Calendar + Reminders access. Call via run_native (runs on the
    worker)."""
    s = store()
    _request_one(s, EK.EKEntityTypeEvent)
    _request_one(s, EK.EKEntityTypeReminder)


def bootstrap() -> None:
    """Startup hook: create the store + request access on the worker. Denial is
    non-fatal."""
    try:
        run_native(request_access)
    except AccessDenied as e:
        log.warning("apple-mcp starting without EventKit access: %s", e)
