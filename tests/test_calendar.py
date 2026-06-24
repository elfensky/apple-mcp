"""Unit tests for the calendar adapter — pure mapping + range parsing (no
EventKit writes)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import Foundation as F
import pytest

from apple_mcp.adapters.calendar import (
    _event_pointer,
    _event_summary,
    _range,
    _resolve_calendar,
)
from apple_mcp.contracts import Pointer


def _ns(dt: datetime):
    return F.NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def _fake_event(title, ident, start, end, all_day=False):
    return SimpleNamespace(
        title=lambda: title,
        calendarItemIdentifier=lambda: ident,
        startDate=lambda: _ns(start),
        endDate=lambda: _ns(end),
        isAllDay=lambda: all_day,
    )


def test_summary_timed():
    e = _fake_event(
        "Standup", "E-1", datetime(2026, 6, 23, 9, 0), datetime(2026, 6, 23, 9, 15)
    )
    assert _event_summary(e) == "Standup 09:00–09:15"


def test_summary_all_day():
    e = _fake_event(
        "Holiday", "E-2", datetime(2026, 6, 23), datetime(2026, 6, 24), all_day=True
    )
    assert _event_summary(e) == "Holiday (all day 2026-06-23)"


def test_pointer_shape():
    start = datetime(2026, 6, 23, 9, 0)
    e = _fake_event("Standup", "E-1", start, datetime(2026, 6, 23, 9, 15))
    p = _event_pointer(e)
    # id = <calendarItemIdentifier>|<occurrence-start-epoch>: addresses one occurrence
    assert isinstance(p, Pointer)
    assert p.id == f"E-1|{int(start.timestamp())}"
    assert p.deeplink.startswith("calshow:")


def test_range_today_is_one_day():
    start, end = _range("today")
    assert (end - start).days == 1 and start.hour == 0


def test_range_explicit_date():
    start, end = _range("2026-12-25")
    assert start == datetime(2026, 12, 25) and (end - start).days == 1


def _fake_store(cal_names, default="Home"):
    cals = [SimpleNamespace(title=lambda n=n: n) for n in cal_names]
    return SimpleNamespace(
        calendarsForEntityType_=lambda _e: cals,
        defaultCalendarForNewEvents=lambda: SimpleNamespace(title=lambda: default),
    )


def test_resolve_named_calendar():
    s = _fake_store(["Work", "Personal"])
    assert _resolve_calendar(s, "Work").title() == "Work"


def test_resolve_default_when_none():
    s = _fake_store(["Work"])
    assert _resolve_calendar(s, None).title() == "Home"


def test_resolve_missing_calendar_raises():
    s = _fake_store(["Work"])
    with pytest.raises(ValueError, match="no calendar named"):
        _resolve_calendar(s, "Nope")
