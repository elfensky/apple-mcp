"""Calendar adapter — EventKit via PyObjC.

Reads return Pointers; writes take ``CalendarEventData``. All EventKit access goes
through ``runtime.run_native``; the store is owned by runtime (shared, not
reached-into).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import EventKit as EK

from ..contracts import CalendarEventData, Pointer
from ..runtime import from_nsdate, run_native, store, to_nsdate


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
    # No public per-event URL scheme; calshow: opens Calendar to the event's day
    # (verify on-device).
    secs = int(item.startDate().timeIntervalSinceReferenceDate())
    return f"calshow:{secs}"


def _event_pointer(item) -> Pointer:
    return Pointer(
        id=item.calendarItemIdentifier(),
        summary=_event_summary(item),
        deeplink=_event_deeplink(item),
    )


def _resolve_calendar(s, name: str | None):
    if name is None:
        return s.defaultCalendarForNewEvents()
    for c in s.calendarsForEntityType_(EK.EKEntityTypeEvent):
        if c.title() == name:
            return c
    raise ValueError(f"no calendar named {name!r}")


def _apply_event(s, e, data: CalendarEventData) -> None:
    e.setTitle_(data.title)
    e.setStartDate_(to_nsdate(data.start))
    e.setEndDate_(to_nsdate(data.end))
    e.setLocation_(data.location)  # full-replace: None clears
    e.setNotes_(data.notes)  # full-replace: None clears
    e.setCalendar_(_resolve_calendar(s, data.calendar))


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

    def create_event(self, data: CalendarEventData) -> Pointer:
        def work():
            s = store()
            e = EK.EKEvent.eventWithEventStore_(s)
            _apply_event(s, e, data)
            ok, err = s.saveEvent_span_commit_error_(e, EK.EKSpanThisEvent, True, None)
            if not ok:
                raise RuntimeError(f"save event failed: {err}")
            return _event_pointer(e)

        return run_native(work)

    def update_event(self, ident: str, data: CalendarEventData) -> Pointer:
        def work():
            s = store()
            e = s.calendarItemWithIdentifier_(ident)
            if e is None:
                raise ValueError(f"no event with id {ident!r}")
            _apply_event(s, e, data)
            ok, err = s.saveEvent_span_commit_error_(e, EK.EKSpanThisEvent, True, None)
            if not ok:
                raise RuntimeError(f"save event failed: {err}")
            return _event_pointer(e)

        return run_native(work)

    def delete_event(self, ident: str) -> None:
        def work():
            s = store()
            e = s.calendarItemWithIdentifier_(ident)
            if e is None:
                raise ValueError(f"no event with id {ident!r}")
            ok, err = s.removeEvent_span_commit_error_(
                e, EK.EKSpanThisEvent, True, None
            )
            if not ok:
                raise RuntimeError(f"delete event failed: {err}")

        run_native(work)
