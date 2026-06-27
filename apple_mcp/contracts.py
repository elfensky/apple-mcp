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
from datetime import UTC, datetime
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
    """Parse an RRULE UNTIL (ISO-8601 or RFC-5545 basic), returned naive-local.

    Two corrections over a bare ``replace(tzinfo=None)``: a tz-aware value (trailing
    ``Z`` / offset) is *converted* to local before the tz is dropped, so the boundary
    names the instant the caller meant rather than shifting by the local offset; and a
    date-only UNTIL resolves to end-of-day, so "until 2026-12-31" still includes a 09:00
    occurrence on the 31st (midnight would drop it).
    """
    s = v.strip()
    parsed = None
    try:
        parsed = datetime.fromisoformat(s)  # ISO incl. trailing Z / offset on 3.11+
    except ValueError:
        for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
            try:
                parsed = datetime.strptime(s, fmt)
                if fmt.endswith("Z"):  # strptime parses the literal Z but stays naive
                    parsed = parsed.replace(tzinfo=UTC)
                break
            except ValueError:
                continue
    if parsed is None:
        raise ValueError(f"recurrence UNTIL is not a recognizable date: {v!r}")
    # tz-aware: convert to local, then go naive — don't just drop the offset
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    if "T" not in s.upper():  # date-only → include the whole final day
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=0)
    return parsed


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
        if count is not None and count < 1:
            raise ValueError(f"RRULE COUNT must be >= 1; got {count}")
        until = _rrule_until(fields["UNTIL"]) if "UNTIL" in fields else None
        return cls(frequency=freq, interval=interval, count=count, until=until)


@dataclass(frozen=True, slots=True)
class ReminderData:
    """Payload for creating/updating an Apple Reminder."""

    title: str
    due: datetime | None = None
    list_name: str | None = None
    notes: str | None = None
    priority: int = 0  # 0 none, 1–9 (1 highest); enforced in __post_init__
    start: datetime | None = None  # start date, distinct from due (None clears)
    recurrence: Recurrence | None = None  # repeat rule (None clears)

    def __post_init__(self) -> None:
        # EventKit rejects a repeating reminder with no due date (EKError 18) — surface
        # it at the boundary as a clear ValueError, not a deep native save failure.
        if self.recurrence is not None and self.due is None:
            raise ValueError("a recurring reminder needs a due date")
        # EventKit priority is 0 (none) or 1–9 (1 highest); enforce on the contract so
        # the invariant holds however ReminderData is built, not only via the MCP tool.
        if not 0 <= self.priority <= 9:
            raise ValueError(
                f"reminder priority must be 0–9 (0=none); got {self.priority}"
            )


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
    # repeat rule; None leaves an existing series rule untouched (unlike the reminder
    # case, an event can't be safely un-recurred through the occurrence-edit path —
    # delete the series instead). See calendar._apply_event.
    recurrence: Recurrence | None = None


@dataclass(frozen=True, slots=True)
class ContactData:
    """Payload for creating an Apple Contact (name + org; v1 keeps it minimal)."""

    given_name: str
    family_name: str | None = None
    organization: str | None = None
