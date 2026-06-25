"""Integration tests — REAL EventKit on this Mac. Run with: uv run pytest -m integration

Never run in CI (no macOS / TCC there). Grant Calendar + Reminders access when first
prompted. Tests create items in the DEFAULT list/calendar with an 'apple-mcp-test:'
title prefix and remove everything they create in teardown.
"""

from __future__ import annotations

import EventKit as EK
import pytest

from apple_mcp.runtime import request_access, run_native, store

TITLE_PREFIX = "apple-mcp-test:"


@pytest.fixture
def created():
    """Track (kind, id) of items a test creates; remove them all afterward."""
    items: list[tuple[str, str]] = []
    yield items

    def _cleanup():
        s = store()
        for kind, ident in items:
            base = (
                ident.rpartition("|")[0] or ident
            )  # event ids carry an occurrence suffix
            obj = s.calendarItemWithIdentifier_(base)
            if obj is None:
                continue
            if kind == "event":
                # FutureEvents removes a recurring series whole, not one occurrence
                s.removeEvent_span_commit_error_(obj, EK.EKSpanFutureEvents, True, None)
            else:
                s.removeReminder_commit_error_(obj, True, None)

    run_native(_cleanup)


@pytest.mark.integration
def test_request_access_grants_full():
    run_native(
        request_access
    )  # raises AccessDenied if not granted — grant when prompted


@pytest.mark.integration
def test_reminders_read_today():
    from apple_mcp.adapters.reminders import RemindersAdapter

    run_native(request_access)
    ptrs = RemindersAdapter().get_pointers("today")
    assert isinstance(ptrs, list)
    for p in ptrs:
        assert p.id and p.summary and p.deeplink.startswith("x-apple-reminderkit://")


@pytest.mark.integration
def test_calendar_read_week():
    from apple_mcp.adapters.calendar import CalendarAdapter

    run_native(request_access)
    ptrs = CalendarAdapter().get_pointers("week")
    assert isinstance(ptrs, list)
    for p in ptrs:
        assert p.id and p.summary and p.deeplink.startswith("calshow:")


@pytest.mark.integration
def test_reminder_create_update_complete(created):
    from datetime import datetime, timedelta

    from apple_mcp.adapters.reminders import RemindersAdapter
    from apple_mcp.contracts import ReminderData

    run_native(request_access)
    a = RemindersAdapter()

    due = datetime.now().replace(microsecond=0) + timedelta(days=1)
    p = a.create_reminder(ReminderData(title=f"{TITLE_PREFIX} v1 round-trip", due=due))
    created.append(("reminder", p.id))
    assert p.id
    assert "due" in p.summary  # created with a due date

    p2 = a.update_reminder(
        p.id, ReminderData(title=f"{TITLE_PREFIX} v1 round-trip (edited)")
    )  # due=None → cleared
    assert p2.id == p.id
    assert "edited" in p2.summary
    assert "due" not in p2.summary  # full-replace cleared the due date

    p3 = a.complete_reminder(p.id)
    assert p3.id == p.id


@pytest.mark.integration
def test_event_create_update_delete(created):
    from datetime import datetime, timedelta

    from apple_mcp.adapters.calendar import CalendarAdapter
    from apple_mcp.contracts import CalendarEventData

    run_native(request_access)
    a = CalendarAdapter()
    start = datetime.now().replace(microsecond=0) + timedelta(days=1)

    p = a.create_event(
        CalendarEventData(
            title=f"{TITLE_PREFIX} v1 event",
            start=start,
            end=start + timedelta(hours=1),
        )
    )
    created.append(("event", p.id))
    assert p.id

    p2 = a.update_event(
        p.id,
        CalendarEventData(
            title=f"{TITLE_PREFIX} v1 event (moved)",
            start=start + timedelta(hours=2),
            end=start + timedelta(hours=3),
        ),
    )
    # moving the event changes the occurrence-id suffix; the base id is unchanged
    assert p2.id.split("|")[0] == p.id.split("|")[0] and "moved" in p2.summary

    a.delete_event(
        p2.id
    )  # delete by the post-move id; teardown is a no-op for an already-deleted id


@pytest.mark.integration
def test_named_list_read_excludes_completed(created):
    """Parity row 4: a named-list read returns only incomplete reminders.

    Mocked-store unit tests can't catch this — it takes a real list with a completed
    item to see the leak. Guards the fix routing the named-list path through the
    incomplete-only selector.
    """
    from apple_mcp.adapters.reminders import RemindersAdapter
    from apple_mcp.contracts import ReminderData

    run_native(request_access)
    a = RemindersAdapter()
    list_name = run_native(lambda: store().defaultCalendarForNewReminders().title())

    open_item = a.create_reminder(
        ReminderData(title=f"{TITLE_PREFIX} open", list_name=list_name)
    )
    created.append(("reminder", open_item.id))
    done_item = a.create_reminder(
        ReminderData(title=f"{TITLE_PREFIX} done", list_name=list_name)
    )
    created.append(("reminder", done_item.id))
    a.complete_reminder(done_item.id)

    ids = [p.id for p in a.get_pointers(list_name)]
    assert open_item.id in ids  # incomplete item is returned
    assert done_item.id not in ids  # completed item is filtered out (the row-4 fix)


@pytest.mark.integration
def test_reminder_lists_enumerate():
    """Parity row 8: enumerate lists; the default list is discoverable by name."""
    from apple_mcp.adapters.reminders import RemindersAdapter

    run_native(request_access)
    ptrs = RemindersAdapter().get_lists()
    assert ptrs and all(p.id and p.summary for p in ptrs)
    default_name = run_native(lambda: store().defaultCalendarForNewReminders().title())
    assert default_name in [p.summary for p in ptrs]


@pytest.mark.integration
def test_calendars_enumerate():
    """Parity row 9: enumerate calendars; the default is discoverable by name."""
    from apple_mcp.adapters.calendar import CalendarAdapter

    run_native(request_access)
    ptrs = CalendarAdapter().get_calendars()
    assert ptrs and all(p.id and p.summary for p in ptrs)
    default_name = run_native(lambda: store().defaultCalendarForNewEvents().title())
    assert default_name in [p.summary for p in ptrs]


@pytest.mark.integration
def test_recurring_event_update_targets_one_occurrence(created):
    """#8: editing by an occurrence's pointer id changes only THAT occurrence.

    The bug a mocked store can't catch: all occurrences share one
    calendarItemIdentifier, so the old calendarItemWithIdentifier_ path edited the
    series master. Create a 3-day daily series, edit the middle occurrence by its
    pointer id, assert days 0 and 2 are untouched.
    """
    from datetime import datetime, timedelta

    from apple_mcp.adapters.calendar import CalendarAdapter
    from apple_mcp.contracts import CalendarEventData
    from apple_mcp.runtime import to_nsdate

    run_native(request_access)
    a = CalendarAdapter()
    days = [
        (datetime.now() + timedelta(days=2)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        + timedelta(days=d)
        for d in range(3)
    ]

    def _make_series():
        s = store()
        e = EK.EKEvent.eventWithEventStore_(s)
        e.setTitle_(f"{TITLE_PREFIX} recurring")
        e.setStartDate_(to_nsdate(days[0]))
        e.setEndDate_(to_nsdate(days[0] + timedelta(hours=1)))
        e.setCalendar_(s.defaultCalendarForNewEvents())
        end = EK.EKRecurrenceEnd.recurrenceEndWithEndDate_(
            to_nsdate(days[2] + timedelta(hours=2))
        )
        rule = EK.EKRecurrenceRule.alloc().initRecurrenceWithFrequency_interval_end_(
            EK.EKRecurrenceFrequencyDaily, 1, end
        )
        e.setRecurrenceRules_([rule])
        ok, err = s.saveEvent_span_commit_error_(e, EK.EKSpanFutureEvents, True, None)
        if not ok:
            raise RuntimeError(f"create recurring failed: {err}")
        return e.calendarItemIdentifier()

    created.append(("event", run_native(_make_series)))

    def titles_on(day):
        return [
            p.summary
            for p in a.get_pointers(day.strftime("%Y-%m-%d"))
            if "recurring" in p.summary
        ]

    mid = [
        p
        for p in a.get_pointers(days[1].strftime("%Y-%m-%d"))
        if "recurring" in p.summary
    ]
    assert len(mid) == 1  # one occurrence on the middle day

    a.update_event(
        mid[0].id,
        CalendarEventData(
            title=f"{TITLE_PREFIX} recurring EDITED",
            start=days[1],
            end=days[1] + timedelta(hours=1),
        ),
    )

    assert any("EDITED" in t for t in titles_on(days[1]))  # middle occurrence changed
    assert all("EDITED" not in t for t in titles_on(days[0]))  # day 0 untouched
    assert all("EDITED" not in t for t in titles_on(days[2]))  # day 2 untouched


@pytest.mark.integration
def test_contacts_create_find_delete():
    """#15: osascript Contacts — create, find by name, delete (Automation TCC)."""
    from apple_mcp.adapters.contacts import ContactsAdapter
    from apple_mcp.contracts import ContactData
    from apple_mcp.runtime import run_osascript

    a = ContactsAdapter()
    p = a.create_contact(
        ContactData(
            given_name="apple-mcp-test",
            family_name="ZZContact",
            organization="apple-mcp",
        )
    )
    try:
        assert p.id and "ZZContact" in p.summary
        assert any(x.id == p.id for x in a.get_pointers("ZZContact"))
    finally:
        run_osascript(
            "on run argv\n"
            '  tell application "Contacts"\n'
            "    delete (first person whose id is (item 1 of argv))\n"
            "    save\n"
            "  end tell\n"
            "end run",
            p.id,
        )


@pytest.mark.integration
def test_files_spotlight_search():
    """#16: Spotlight (mdfind) finds files by name. Needs a populated index."""
    from apple_mcp.adapters.files import FilesAdapter

    ptrs = FilesAdapter().get_pointers("pyproject.toml")
    assert ptrs and all(p.id.startswith("/") and p.summary for p in ptrs)
    assert any(p.summary == "pyproject.toml" for p in ptrs)


@pytest.mark.integration
def test_mail_search_runs():
    """#18: Mail subject search via osascript runs (Automation TCC)."""
    from apple_mcp.adapters.mail import MailAdapter

    ptrs = MailAdapter().get_pointers("apple-mcp-no-such-subject-zzz")
    assert isinstance(
        ptrs, list
    )  # runs without error (likely empty) — validates the path
