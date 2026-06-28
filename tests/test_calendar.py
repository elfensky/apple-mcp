"""Unit tests for the calendar adapter — pure mapping + range parsing (no
EventKit writes)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import Foundation as F
import pytest

from mac_mcp.adapters.calendar import (
    _all_day_bounds,
    _event_pointer,
    _event_summary,
    _range,
    _resolve_calendar,
)
from mac_mcp.contracts import Pointer


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


def test_all_day_bounds_same_day_stays_one_day():
    # a timed same-day range → date-only bounds with end == start. EventKit's all-day
    # end is inclusive (verified on-device), so end == start IS a single day — bumping
    # it a day would make a 2-day event.
    s, e = _all_day_bounds(datetime(2026, 7, 1, 9, 30), datetime(2026, 7, 1, 10, 45))
    assert s == datetime(2026, 7, 1)
    assert e == datetime(2026, 7, 1)


def test_all_day_bounds_preserves_multiday_span():
    # Jul 1 09:00 → Jul 3 10:00 spans 3 calendar days; inclusive end keeps end == Jul 3.
    s, e = _all_day_bounds(datetime(2026, 7, 1, 9, 0), datetime(2026, 7, 3, 10, 0))
    assert s == datetime(2026, 7, 1) and e == datetime(2026, 7, 3)


def test_all_day_bounds_clamps_reversed_span_to_one_day():
    # a genuinely reversed range (end before start) clamps to a single day, not an
    # invalid reversed span handed to EventKit.
    s, e = _all_day_bounds(datetime(2026, 7, 10), datetime(2026, 7, 5))
    assert s == datetime(2026, 7, 10) and e == datetime(2026, 7, 10)


def test_all_day_bounds_drops_tzinfo_so_mixed_naive_aware_cannot_crash():
    # a tz-aware start + naive end (each parsed independently at the tool boundary) must
    # not raise on the e < s compare; all-day bounds are a date, so tz is dropped.
    aware = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
    s, e = _all_day_bounds(aware, datetime(2026, 7, 1, 10, 0))
    assert s == datetime(2026, 7, 1) and e == datetime(2026, 7, 1)
    assert s.tzinfo is None and e.tzinfo is None


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
