"""Adapter contracts — the boundary every Apple-app adapter implements.

Settled by design (adversarial debate): **reads are uniform, writes are per-adapter typed.**

- Every adapter is a ``PointerSource``: ``get_pointers(query) -> list[Pointer]``. That is the only
  shape the cockpit needs on the read side (surface *what exists*, as citable handles).
- Writes are **typed per-adapter methods** (``create_reminder(ReminderData)``,
  ``create_event(CalendarEventData)``) — never a stringly-typed ``create_item(dict)``, which rots
  into ``list`` vs ``list_id`` vs ``listId`` and is invisible to the type checker.

``Pointer`` mirrors the cockpit's citation grammar (``conventions.md``: ``[src:: system:id]`` + an
open-in-app deeplink) — *pointers, not payload*: a citable handle, never the full body.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Pointer:
    """A citable handle to one external instance — never the full body.

    ``id``       stable source id, captured at pull time (the "Connector law").
    ``summary``  short citable extract (embeddable, auditable).
    ``deeplink`` open-in-app URL, e.g. ``x-apple-reminderkit://…`` / ``ical://…``.
    """

    id: str
    summary: str
    deeplink: str


@runtime_checkable
class PointerSource(Protocol):
    """The uniform READ side: every adapter answers queries with Pointers.

    Structural (``Protocol``), not an ABC — fakes satisfy it without inheritance, which is what
    keeps the tool layer unit-testable by mocking at this boundary.
    """

    def get_pointers(self, query: str) -> list[Pointer]: ...


# --- per-adapter typed WRITE payloads (reads uniform, writes typed) -----------------------------

@dataclass(frozen=True, slots=True)
class ReminderData:
    """Payload for creating/updating an Apple Reminder."""

    title: str
    due: datetime | None = None
    list_name: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class CalendarEventData:
    """Payload for creating/updating an Apple Calendar event."""

    title: str
    start: datetime
    end: datetime
    calendar: str | None = None
    location: str | None = None
    notes: str | None = None
