"""Unit tests for the adapter contract + native runtime — the test seam is the
adapter boundary."""

from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from apple_mcp.contracts import (
    CalendarEventData,
    Pointer,
    PointerSource,
    Recurrence,
    ReminderData,
)
from apple_mcp.runtime import run_native


class FakeReminders:
    """Satisfies PointerSource structurally — no native calls. This is how the
    tool layer is mocked."""

    def get_pointers(self, query: str) -> list[Pointer]:
        return [
            Pointer(
                id="x-1",
                summary=f"reminder ~ {query}",
                deeplink="x-apple-reminderkit://x-1",
            )
        ]


def test_fake_satisfies_pointersource():
    fake = FakeReminders()
    assert isinstance(
        fake, PointerSource
    )  # runtime_checkable structural match — no inheritance
    ptrs = fake.get_pointers("dentist")
    assert ptrs[0].id == "x-1"
    assert ptrs[0].deeplink.startswith("x-apple")


def test_pointer_is_frozen():
    p = Pointer(id="a", summary="s", deeplink="d")
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.id = "b"  # type: ignore[misc]


def test_typed_write_payload_defaults():
    r = ReminderData(title="Call dentist")
    assert r.due is None and r.list_name is None
    assert r.priority == 0 and r.start is None  # unset = no priority, no start date
    assert r.recurrence is None

    e = CalendarEventData(
        title="Standup",
        start=datetime(2026, 6, 24, 9),
        end=datetime(2026, 6, 24, 9, 15),
    )
    assert e.calendar is None and e.location is None
    assert e.all_day is False and e.recurrence is None


def test_recurrence_from_rrule_basic():
    assert Recurrence.from_rrule("FREQ=WEEKLY;INTERVAL=2;COUNT=10") == Recurrence(
        frequency="weekly", interval=2, count=10
    )


def test_recurrence_defaults_interval_to_one():
    assert Recurrence.from_rrule("FREQ=DAILY").interval == 1


def test_recurrence_until_rfc5545_basic():
    r = Recurrence.from_rrule("FREQ=MONTHLY;UNTIL=20261231T000000Z")
    assert r.frequency == "monthly" and r.until == datetime(2026, 12, 31)


def test_recurrence_until_iso():
    assert Recurrence.from_rrule("FREQ=DAILY;UNTIL=2026-12-31").until == datetime(
        2026, 12, 31
    )


def test_recurrence_strips_rrule_prefix():
    assert Recurrence.from_rrule("RRULE:FREQ=YEARLY").frequency == "yearly"


def test_recurrence_rejects_unknown_freq():
    with pytest.raises(ValueError, match="FREQ must be"):
        Recurrence.from_rrule("FREQ=HOURLY")


def test_recurrence_rejects_unsupported_part():
    with pytest.raises(ValueError, match="unsupported RRULE"):
        Recurrence.from_rrule("FREQ=WEEKLY;BYDAY=MO")


def test_recurrence_rejects_count_and_until_together():
    with pytest.raises(ValueError, match="mutually exclusive"):
        Recurrence.from_rrule("FREQ=DAILY;COUNT=5;UNTIL=2026-12-31")


def test_recurrence_rejects_malformed_part():
    with pytest.raises(ValueError, match="expected KEY=VALUE"):
        Recurrence.from_rrule("FREQ=DAILY;GARBAGE")


def test_reminder_recurrence_requires_due():
    with pytest.raises(ValueError, match="needs a due date"):
        ReminderData(title="Standup", recurrence=Recurrence(frequency="daily"))


def test_run_native_runs_on_worker():
    assert run_native(lambda: 2 + 2) == 4
