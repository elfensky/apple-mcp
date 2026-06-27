"""Calendar adapter — EventKit via PyObjC.

Reads return Pointers; writes take ``CalendarEventData``. All EventKit access goes
through ``runtime.run_native``; the store is owned by runtime (shared, not
reached-into).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import EventKit as EK

from ..contracts import CalendarEventData, Pointer
from ..runtime import (
    from_nsdate,
    run_native,
    store,
    to_nsdate,
    to_recurrence_rule,
)


def _range(query: str) -> tuple[datetime, datetime]:
    q = query.strip().lower()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if q == "today":
        return today, today + timedelta(days=1)
    if q == "week":
        return today, today + timedelta(days=7)
    day = datetime.fromisoformat(query.strip()).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return day, day + timedelta(days=1)


def _event_summary(item) -> str:
    start = from_nsdate(item.startDate())
    if item.isAllDay():
        return f"{item.title()} (all day {start:%Y-%m-%d})"
    end = from_nsdate(item.endDate())
    return f"{item.title()} {start:%H:%M}–{end:%H:%M}"


def _event_deeplink(item) -> str:
    # calshow:<seconds-since-2001> opens Calendar to the event's day/time. macOS has no
    # public scheme to open a *specific* event by id (x-apple-calevent:// is rejected;
    # eventIdentifier isn't URL-addressable, and is occurrence-shared). See Apple Dev
    # Forums #759266. Co-starting events thus share a deeplink; the Pointer summary +
    # occurrence-precise id (see _event_id) disambiguate, not the link.
    secs = int(item.startDate().timeIntervalSinceReferenceDate())
    return f"calshow:{secs}"


# Recurring events share ONE calendarItemIdentifier across every occurrence, so the
# bare id can't name a single occurrence. Carry the occurrence start (epoch seconds) in
# the pointer id and re-fetch the concrete EKEvent on write (see _resolve_event), so
# EKSpanThisEvent targets THAT occurrence.
_OCC_SEP = "|"


def _event_id(item) -> str:
    base = item.calendarItemIdentifier()
    epoch = int(item.startDate().timeIntervalSince1970())
    return f"{base}{_OCC_SEP}{epoch}"


def _event_pointer(item) -> Pointer:
    return Pointer(
        id=_event_id(item),
        summary=_event_summary(item),
        deeplink=_event_deeplink(item),
    )


def _calendar_pointer(cal) -> Pointer:
    # A calendar (container) has no public per-calendar URL scheme; id + name (summary)
    # are what the projection resolves a write target against. deeplink empty by design.
    return Pointer(id=cal.calendarIdentifier(), summary=cal.title(), deeplink="")


def _resolve_calendar(s, name: str | None):
    if name is None:
        return s.defaultCalendarForNewEvents()
    for c in s.calendarsForEntityType_(EK.EKEntityTypeEvent):
        if c.title() == name:
            return c
    raise ValueError(f"no calendar named {name!r}")


def _apply_event(s, e, data: CalendarEventData) -> None:
    e.setTitle_(data.title)
    e.setAllDay_(data.all_day)
    e.setStartDate_(to_nsdate(data.start))
    e.setEndDate_(to_nsdate(data.end))
    e.setLocation_(data.location)  # full-replace: None clears
    e.setNotes_(data.notes)  # full-replace: None clears
    # Recurrence is the exception to full-replace: only SET it when provided. Clearing a
    # series needs EKSpanFutureEvents (see _span), but an omitted recurrence means "edit
    # this occurrence" (EKSpanThisEvent) — so clearing-on-None would silently detach one
    # occurrence and leave the series recurring. Leave the rule untouched instead.
    if data.recurrence is not None:
        e.setRecurrenceRules_([to_recurrence_rule(data.recurrence)])
    e.setCalendar_(_resolve_calendar(s, data.calendar))


def _span(data: CalendarEventData):
    # A recurrence change defines the whole series, so it must span future events; a
    # plain edit stays on the single cited occurrence (see _resolve_event).
    return EK.EKSpanFutureEvents if data.recurrence else EK.EKSpanThisEvent


def _resolve_event(s, ident: str):
    """Resolve a pointer id to the concrete EKEvent (specific occurrence if recurring).

    Pointer ids are ``<calendarItemIdentifier>|<occurrence-start-epoch>``.
    ``calendarItemWithIdentifier_`` returns the series *master* (shared across
    occurrences), so editing/deleting it with EKSpanThisEvent hits the wrong occurrence.
    Re-fetch via a tight date-range predicate and match on (calendarItemIdentifier,
    start) so the write targets exactly the cited occurrence.
    """
    base, sep, occ = ident.rpartition(_OCC_SEP)
    if (
        not sep
    ):  # legacy/plain id (no occurrence suffix) — fall back to the master lookup
        e = s.calendarItemWithIdentifier_(ident)
        if e is None:
            raise ValueError(f"no event with id {ident!r}")
        return e
    occ_epoch = int(occ)
    occ_start = datetime.fromtimestamp(occ_epoch)
    pred = s.predicateForEventsWithStartDate_endDate_calendars_(
        to_nsdate(occ_start - timedelta(seconds=1)),
        to_nsdate(occ_start + timedelta(seconds=1)),
        None,
    )
    for e in s.eventsMatchingPredicate_(pred) or []:
        if (
            e.calendarItemIdentifier() == base
            and int(e.startDate().timeIntervalSince1970()) == occ_epoch
        ):
            return e
    raise ValueError(f"no event occurrence for id {ident!r}")


class CalendarAdapter:
    def get_pointers(self, query: str) -> list[Pointer]:
        """query: 'today' | 'week' | 'YYYY-MM-DD'."""

        def work():
            s = store()
            start, end = _range(query)
            pred = s.predicateForEventsWithStartDate_endDate_calendars_(
                to_nsdate(start), to_nsdate(end), None
            )
            return [_event_pointer(e) for e in (s.eventsMatchingPredicate_(pred) or [])]

        return run_native(work)

    def get_calendars(self) -> list[Pointer]:
        """Enumerate calendars as Pointers (id + name) for resolving write targets."""

        def work():
            s = store()
            return [
                _calendar_pointer(c)
                for c in s.calendarsForEntityType_(EK.EKEntityTypeEvent)
            ]

        return run_native(work)

    def create_event(self, data: CalendarEventData) -> Pointer:
        def work():
            s = store()
            e = EK.EKEvent.eventWithEventStore_(s)
            _apply_event(s, e, data)
            ok, err = s.saveEvent_span_commit_error_(e, _span(data), True, None)
            if not ok:
                raise RuntimeError(f"save event failed: {err}")
            return _event_pointer(e)

        return run_native(work)

    def update_event(self, ident: str, data: CalendarEventData) -> Pointer:
        def work():
            s = store()
            e = _resolve_event(s, ident)
            _apply_event(s, e, data)
            ok, err = s.saveEvent_span_commit_error_(e, _span(data), True, None)
            if not ok:
                raise RuntimeError(f"save event failed: {err}")
            return _event_pointer(e)

        return run_native(work)

    def delete_event(self, ident: str) -> None:
        def work():
            s = store()
            e = _resolve_event(s, ident)
            ok, err = s.removeEvent_span_commit_error_(
                e, EK.EKSpanThisEvent, True, None
            )
            if not ok:
                raise RuntimeError(f"delete event failed: {err}")

        run_native(work)
