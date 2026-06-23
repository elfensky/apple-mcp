"""Native-call runtime: serialize ALL EventKit access onto ONE dedicated thread.

Settled by design (adversarial debate). ``EKEventStore`` has **thread affinity** (it must be
accessed from the thread that created it) and **TCC** authorization must be handled on a consistent
thread. A generic ``asyncio.to_thread`` / default multi-worker pool scatters calls across threads →
affinity bugs and a hung first-permission prompt. So every native call goes through a single
``max_workers=1`` executor; the ``EKEventStore`` itself is created *inside* that worker at startup
(done by the adapters — see GitHub issues).

This is user-latency-bound, not throughput-bound, so serialization costs nothing in practice.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

import EventKit as EK

T = TypeVar("T")

# ponytail: one process-wide native thread. If a future app needs a *second* isolated native
# context, give it its own executor — don't widen this one to max_workers>1 (breaks EKEventStore).
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="apple-native")


def run_native(fn: Callable[[], T]) -> T:
    """Run a blocking native callable on the single dedicated worker thread and return its result.

    Adapters wrap every EventKit / osascript call in this so the work always lands on one thread,
    regardless of which thread FastMCP invoked the tool from.
    """
    return _executor.submit(fn).result()


_FULL_ACCESS = EK.EKAuthorizationStatusFullAccess  # == 3 on macOS 14+


class AccessDenied(RuntimeError):
    """Raised when Calendar/Reminders TCC access is not fully granted."""


def _decide(status: int) -> None:
    """Map an EKAuthorizationStatus to a decision: return on full access, else raise."""
    if status == _FULL_ACCESS:
        return
    raise AccessDenied(
        "apple-mcp needs Calendar + Reminders access. Grant it in "
        "System Settings → Privacy & Security → Calendars and Reminders, then restart apple-mcp."
    )
