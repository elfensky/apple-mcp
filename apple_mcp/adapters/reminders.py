"""Reminders adapter — EventKit via PyObjC.

Reads return Pointers; writes take ``ReminderData``. All EventKit access goes through
``runtime.run_native`` (single serialized worker), and the store is owned by runtime.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import EventKit as EK

from ..contracts import Pointer, ReminderData
from ..runtime import due_components, run_native, run_native_async, store, to_nsdate

# A fetch has no user interaction, so the GCD callback should arrive quickly. Bound the
# wait so a callback that never fires can't hang the single worker — and every later
# run_native — forever.
_FETCH_TIMEOUT = 30.0  # seconds


def _reminder_summary(item) -> str:
    due = item.dueDateComponents()
    if due is not None:
        return (
            f"{item.title()} — due {due.year():04d}-{due.month():02d}-{due.day():02d}"
        )
    return item.title()


def _reminder_deeplink(ident: str) -> str:
    # Best-effort scheme; verify on-device that it opens the item (DESIGN: deeplinks are
    # a calibration knob).
    return f"x-apple-reminderkit://REMCDReminder/{ident}"


def _reminder_pointer(item) -> Pointer:
    ident = item.calendarItemIdentifier()
    return Pointer(
        id=ident, summary=_reminder_summary(item), deeplink=_reminder_deeplink(ident)
    )


def _list_pointer(cal) -> Pointer:
    # A reminder list (container) has no verified open-in-app URL; id + name (summary)
    # are what the projection resolves a write target against. ponytail: deeplink empty
    # by design — if on-device testing finds a working list URL, set it here (deeplinks
    # are a calibration knob).
    return Pointer(id=cal.calendarIdentifier(), summary=cal.title(), deeplink="")


def _fetch_reminders(s, predicate) -> list:
    """fetchRemindersMatchingPredicate_completion_ is async — block on the callback."""

    def start(finish):
        s.fetchRemindersMatchingPredicate_completion_(
            predicate, lambda reminders: finish(list(reminders or []))
        )

    return run_native_async(start, timeout=_FETCH_TIMEOUT)


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=0)


def _incomplete_due_pred(s, end: datetime | None, cals):
    """Incomplete reminders due up to ``end`` (no lower bound, start=None).

    ``end=None`` → all incomplete reminders regardless of due date. The named-list path
    relies on this: the old ``predicateForRemindersInCalendars_`` leaked completed items
    (parity row 4), so every reminder read routes through this one incomplete-only
    selector.
    """
    return s.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
        None, to_nsdate(end) if end is not None else None, cals
    )


def _resolve_list(s, name: str | None):
    if name is None:
        return s.defaultCalendarForNewReminders()
    for c in s.calendarsForEntityType_(EK.EKEntityTypeReminder):
        if c.title() == name:
            return c
    raise ValueError(f"no reminder list named {name!r}")


def _apply_reminder(s, r, data: ReminderData) -> None:
    r.setTitle_(data.title)
    r.setNotes_(data.notes)  # full-replace: None clears
    r.setDueDateComponents_(due_components(data.due) if data.due is not None else None)
    r.setCalendar_(_resolve_list(s, data.list_name))


class RemindersAdapter:
    def get_pointers(self, query: str) -> list[Pointer]:
        """query: 'today' | 'overdue' | 'this-week' | a reminder-list name."""

        def work():
            s = store()
            cals = s.calendarsForEntityType_(EK.EKEntityTypeReminder)
            q = query.strip().lower()
            if q in ("today", "overdue", "this-week"):
                now = datetime.now()
                end = {
                    "today": _end_of_day(now),
                    "overdue": now,
                    "this-week": now + timedelta(days=7),
                }[q]
                # No lower bound (start=None) is intentional: each selector wants all
                # incomplete reminders due up to `end`, so overdue ⊂ today ⊂ this-week.
                # The briefing relies on this.
                pred = _incomplete_due_pred(s, end, cals)
            else:
                name = query.strip()
                named = [c for c in cals if c.title() == name]
                if not named:
                    raise ValueError(f"no reminder list named {name!r}")
                # Incomplete-only (both bounds nil), same selector as the date
                # paths — predicateForRemindersInCalendars_ leaked completed items
                # (parity row 4).
                pred = _incomplete_due_pred(s, None, named)
            return [_reminder_pointer(r) for r in _fetch_reminders(s, pred)]

        return run_native(work)

    def get_lists(self) -> list[Pointer]:
        """Reminder lists as Pointers (id + name) for resolving write targets."""

        def work():
            s = store()
            return [
                _list_pointer(c)
                for c in s.calendarsForEntityType_(EK.EKEntityTypeReminder)
            ]

        return run_native(work)

    def create_reminder(self, data: ReminderData) -> Pointer:
        def work():
            s = store()
            r = EK.EKReminder.reminderWithEventStore_(s)
            _apply_reminder(s, r, data)
            ok, err = s.saveReminder_commit_error_(r, True, None)
            if not ok:
                raise RuntimeError(f"save reminder failed: {err}")
            return _reminder_pointer(r)

        return run_native(work)

    def update_reminder(self, ident: str, data: ReminderData) -> Pointer:
        def work():
            s = store()
            r = s.calendarItemWithIdentifier_(ident)
            if r is None:
                raise ValueError(f"no reminder with id {ident!r}")
            _apply_reminder(s, r, data)
            ok, err = s.saveReminder_commit_error_(r, True, None)
            if not ok:
                raise RuntimeError(f"save reminder failed: {err}")
            return _reminder_pointer(r)

        return run_native(work)

    def complete_reminder(self, ident: str) -> Pointer:
        def work():
            s = store()
            r = s.calendarItemWithIdentifier_(ident)
            if r is None:
                raise ValueError(f"no reminder with id {ident!r}")
            r.setCompleted_(True)
            ok, err = s.saveReminder_commit_error_(r, True, None)
            if not ok:
                raise RuntimeError(f"complete reminder failed: {err}")
            return _reminder_pointer(r)

        return run_native(work)
