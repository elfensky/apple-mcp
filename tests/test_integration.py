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
            obj = s.calendarItemWithIdentifier_(ident)
            if obj is None:
                continue
            if kind == "event":
                s.removeEvent_span_commit_error_(obj, EK.EKSpanThisEvent, True, None)
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
    assert p2.id == p.id and "moved" in p2.summary

    a.delete_event(
        p.id
    )  # explicit delete; teardown is a no-op for an already-deleted id


@pytest.mark.integration
def test_named_list_read_excludes_completed(created):
    """Parity row 4: a named-list read must return only incomplete reminders, never completed.

    Mocked-store unit tests can't catch this — it takes a real list with a completed item to see
    the leak. Guards the fix that routed the named-list path through the incomplete-only selector.
    """
    from apple_mcp.adapters.reminders import RemindersAdapter
    from apple_mcp.contracts import ReminderData

    run_native(request_access)
    a = RemindersAdapter()
    list_name = run_native(lambda: store().defaultCalendarForNewReminders().title())

    open_item = a.create_reminder(ReminderData(title=f"{TITLE_PREFIX} open", list_name=list_name))
    created.append(("reminder", open_item.id))
    done_item = a.create_reminder(ReminderData(title=f"{TITLE_PREFIX} done", list_name=list_name))
    created.append(("reminder", done_item.id))
    a.complete_reminder(done_item.id)

    ids = [p.id for p in a.get_pointers(list_name)]
    assert open_item.id in ids  # incomplete item is returned
    assert done_item.id not in ids  # completed item is filtered out (the row-4 fix)
