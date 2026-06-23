"""Unit tests for the reminders adapter — pure mapping only (fakes, no EventKit)."""
from __future__ import annotations

from types import SimpleNamespace

from apple_mcp.adapters.reminders import _reminder_deeplink, _reminder_pointer, _reminder_summary
from apple_mcp.contracts import Pointer


def _fake_reminder(title, ident, due=None):
    due_comps = None
    if due is not None:
        y, m, d = due
        due_comps = SimpleNamespace(year=lambda: y, month=lambda: m, day=lambda: d)
    return SimpleNamespace(
        title=lambda: title,
        calendarItemIdentifier=lambda: ident,
        dueDateComponents=lambda: due_comps,
    )


def test_summary_with_due():
    item = _fake_reminder("Call dentist", "R-1", due=(2026, 6, 23))
    assert _reminder_summary(item) == "Call dentist — due 2026-06-23"


def test_summary_without_due():
    assert _reminder_summary(_fake_reminder("Buy milk", "R-2")) == "Buy milk"


def test_deeplink_format():
    assert _reminder_deeplink("R-1") == "x-apple-reminderkit://REMCDReminder/R-1"


def test_pointer_shape():
    p = _reminder_pointer(_fake_reminder("Call dentist", "R-1", due=(2026, 6, 23)))
    assert isinstance(p, Pointer)
    assert p.id == "R-1" and p.summary.startswith("Call dentist") and p.deeplink.endswith("/R-1")
