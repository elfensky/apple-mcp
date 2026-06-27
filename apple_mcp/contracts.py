"""Adapter contracts — the boundary every Apple-app adapter implements.

Settled by design (adversarial debate): **reads are uniform, writes are per-adapter
typed.**

- Every adapter is a ``PointerSource``: ``get_pointers(query) -> list[Pointer]``. That
  is the only shape the cockpit needs on the read side (surface *what exists*, as
  citable handles).
- Writes are **typed per-adapter methods** (``create_reminder(ReminderData)``,
  ``create_event(CalendarEventData)``) — never a stringly-typed ``create_item(dict)``,
  which rots into ``list`` vs ``list_id`` vs ``listId`` and is invisible to the type
  checker.

``Pointer`` mirrors the cockpit's citation grammar (``conventions.md``: ``[src::
system:id]`` + an open-in-app deeplink) — *pointers, not payload*: a citable handle,
never the full body.
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

    Structural (``Protocol``), not an ABC — fakes satisfy it without inheritance, which
    is what keeps the tool layer unit-testable by mocking at this boundary.
    """

    def get_pointers(self, query: str) -> list[Pointer]: ...


# --- per-adapter typed WRITE payloads (reads uniform, writes typed) ------------------

_FREQUENCIES = ("daily", "weekly", "monthly", "yearly")
_RRULE_SUPPORTED = ("FREQ", "INTERVAL", "COUNT", "UNTIL")


def _rrule_until(v: str) -> datetime:
    """Parse an RRULE UNTIL (ISO-8601 or RFC-5545 basic), returned naive.

    fromisoformat turns a trailing ``Z`` into a tz-aware value; the rest of the codebase
    is naive-local, so drop the tzinfo to stay comparable (UNTIL is a coarse bound).
    """
    parsed = None
    try:
        parsed = datetime.fromisoformat(v)  # ISO incl. trailing Z on 3.11+
    except ValueError:
        for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
            try:
                parsed = datetime.strptime(v, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        raise ValueError(f"recurrence UNTIL is not a recognizable date: {v!r}")
    return parsed.replace(tzinfo=None)


@dataclass(frozen=True, slots=True)
class Recurrence:
    """A repeat rule — the FREQ/INTERVAL/COUNT/UNTIL subset of RFC 5545.

    Pure data: the EventKit ``EKRecurrenceRule`` mapping lives in
    ``runtime.to_recurrence_rule``, so this module stays free of native imports.
    """

    frequency: str  # daily | weekly | monthly | yearly
    interval: int = 1  # every N periods
    count: int | None = None  # end after N occurrences …
    until: datetime | None = None  # … or end on a date (mutually exclusive with count)

    @classmethod
    def from_rrule(cls, rrule: str) -> Recurrence:
        """Parse an RFC 5545 RRULE (the supported subset).

        e.g. ``FREQ=WEEKLY;INTERVAL=2;COUNT=10``. FREQ is required; COUNT and UNTIL are
        mutually exclusive. Unsupported parts (BYDAY, BYMONTHDAY, …) are rejected so a
        rule never silently does the wrong thing.
        """
        body = rrule.strip()
        if body.upper().startswith("RRULE:"):
            body = body[6:]
        fields: dict[str, str] = {}
        for token in body.split(";"):
            token = token.strip()
            if not token:
                continue
            if "=" not in token:
                raise ValueError(f"bad RRULE part {token!r} (expected KEY=VALUE)")
            key, _, val = token.partition("=")
            fields[key.strip().upper()] = val.strip()

        extra = set(fields) - set(_RRULE_SUPPORTED)
        if extra:
            raise ValueError(
                f"unsupported RRULE part(s): {', '.join(sorted(extra))} "
                f"(supported: {', '.join(_RRULE_SUPPORTED)})"
            )
        freq = fields.get("FREQ", "").lower()
        if freq not in _FREQUENCIES:
            raise ValueError(
                f"RRULE FREQ must be one of {_FREQUENCIES}; got {fields.get('FREQ')!r}"
            )
        interval = int(fields["INTERVAL"]) if "INTERVAL" in fields else 1
        if interval < 1:
            raise ValueError(f"RRULE INTERVAL must be >= 1; got {interval}")
        if "COUNT" in fields and "UNTIL" in fields:
            raise ValueError("RRULE COUNT and UNTIL are mutually exclusive")
        count = int(fields["COUNT"]) if "COUNT" in fields else None
        until = _rrule_until(fields["UNTIL"]) if "UNTIL" in fields else None
        return cls(frequency=freq, interval=interval, count=count, until=until)


@dataclass(frozen=True, slots=True)
class ReminderData:
    """Payload for creating/updating an Apple Reminder."""

    title: str
    due: datetime | None = None
    list_name: str | None = None
    notes: str | None = None
    priority: int = 0  # 0 none, 1–9 (1 highest); checked at the tool boundary
    start: datetime | None = None  # start date, distinct from due (None clears)
    recurrence: Recurrence | None = None  # repeat rule (None clears)

    def __post_init__(self) -> None:
        # EventKit rejects a repeating reminder with no due date (EKError 18) — surface
        # it at the boundary as a clear ValueError, not a deep native save failure.
        if self.recurrence is not None and self.due is None:
            raise ValueError("a recurring reminder needs a due date")


@dataclass(frozen=True, slots=True)
class CalendarEventData:
    """Payload for creating/updating an Apple Calendar event."""

    title: str
    start: datetime
    end: datetime
    calendar: str | None = None
    location: str | None = None
    notes: str | None = None
    all_day: bool = False
    recurrence: Recurrence | None = None  # repeat rule (None clears)


@dataclass(frozen=True, slots=True)
class ContactData:
    """Payload for creating an Apple Contact (name + org; v1 keeps it minimal)."""

    given_name: str
    family_name: str | None = None
    organization: str | None = None
