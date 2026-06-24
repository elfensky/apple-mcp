"""Unit tests for the adapter contract + native runtime — the test seam is the
adapter boundary."""

from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from apple_mcp.contracts import CalendarEventData, Pointer, PointerSource, ReminderData
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

    e = CalendarEventData(
        title="Standup",
        start=datetime(2026, 6, 24, 9),
        end=datetime(2026, 6, 24, 9, 15),
    )
    assert e.calendar is None and e.location is None


def test_run_native_runs_on_worker():
    assert run_native(lambda: 2 + 2) == 4
