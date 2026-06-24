"""apple-mcp — FastMCP server.

Tools are *thin dispatch* to adapters (see contracts.py).
"""

from __future__ import annotations

from datetime import datetime

from fastmcp import FastMCP

from .adapters.calendar import CalendarAdapter
from .adapters.reminders import RemindersAdapter
from .contracts import CalendarEventData, Pointer, ReminderData

mcp = FastMCP("apple-mcp")

_reminders = RemindersAdapter()
_calendar = CalendarAdapter()


def _emit(p: Pointer) -> dict[str, str]:
    return {"id": p.id, "summary": p.summary, "deeplink": p.deeplink}


@mcp.tool()
def ping() -> str:
    """Health check — confirms apple-mcp is alive."""
    return "apple-mcp ok"


@mcp.tool()
def reminders(due: str = "today") -> list[dict]:
    """List reminders as pointers. `due`: today | overdue | this-week | a list name."""
    return [_emit(p) for p in _reminders.get_pointers(due)]


@mcp.tool()
def events(when: str = "today") -> list[dict]:
    """List calendar events as pointers. `when`: today | week | YYYY-MM-DD."""
    return [_emit(p) for p in _calendar.get_pointers(when)]


def _parse(s: str | None) -> datetime | None:
    """Optional ISO datetime (reminder due). Empty/absent → None."""
    return datetime.fromisoformat(s) if s else None


def _parse_required(label: str, s: str) -> datetime:
    """Required ISO datetime (event start/end).

    Bad/empty input fails clearly at the tool boundary.
    """
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"{label} must be an ISO datetime string "
            f"(e.g. 2026-06-24T09:00:00), got {s!r}"
        ) from e


@mcp.tool()
def create_reminder(
    title: str,
    due: str | None = None,
    list_name: str | None = None,
    notes: str | None = None,
) -> dict:
    """Create a reminder. `due` is an ISO datetime string (e.g. 2026-06-23T18:00:00)."""
    data = ReminderData(title=title, due=_parse(due), list_name=list_name, notes=notes)
    return _emit(_reminders.create_reminder(data))


@mcp.tool()
def update_reminder(
    id: str,
    title: str,
    due: str | None = None,
    list_name: str | None = None,
    notes: str | None = None,
) -> dict:
    """Update a reminder by id (full replace from the given fields)."""
    data = ReminderData(title=title, due=_parse(due), list_name=list_name, notes=notes)
    return _emit(_reminders.update_reminder(id, data))


@mcp.tool()
def complete_reminder(id: str) -> dict:
    """Mark a reminder complete by id."""
    return _emit(_reminders.complete_reminder(id))


@mcp.tool()
def create_event(
    title: str,
    start: str,
    end: str,
    calendar: str | None = None,
    location: str | None = None,
    notes: str | None = None,
) -> dict:
    """Create a calendar event. `start`/`end` are ISO datetime strings."""
    data = CalendarEventData(
        title=title,
        start=_parse_required("start", start),
        end=_parse_required("end", end),
        calendar=calendar,
        location=location,
        notes=notes,
    )
    return _emit(_calendar.create_event(data))


@mcp.tool()
def update_event(
    id: str,
    title: str,
    start: str,
    end: str,
    calendar: str | None = None,
    location: str | None = None,
    notes: str | None = None,
) -> dict:
    """Update an event by id (full replace from the given fields)."""
    data = CalendarEventData(
        title=title,
        start=_parse_required("start", start),
        end=_parse_required("end", end),
        calendar=calendar,
        location=location,
        notes=notes,
    )
    return _emit(_calendar.update_event(id, data))


@mcp.tool()
def delete_event(id: str) -> dict:
    """Delete a calendar event by id."""
    _calendar.delete_event(id)
    return {"deleted": id}


def main() -> None:
    """Console entry point (`apple-mcp`) and `python -m apple_mcp`."""
    from .runtime import bootstrap

    bootstrap()
    mcp.run()  # stdio transport
