"""apple-mcp — FastMCP server.

Tools are *thin dispatch* to adapters (see contracts.py). Set APPLE_MCP_READ_ONLY=1 to
register reads only (the destructive write tools are skipped) — a safe-deploy guard.
"""

from __future__ import annotations

import os
from datetime import datetime

from fastmcp import FastMCP

from .adapters.calendar import CalendarAdapter
from .adapters.contacts import ContactsAdapter
from .adapters.files import FilesAdapter
from .adapters.mail import MailAdapter
from .adapters.maps import MapsAdapter
from .adapters.notes import NotesAdapter
from .adapters.reminders import RemindersAdapter
from .contracts import CalendarEventData, ContactData, Pointer, ReminderData

mcp = FastMCP("apple-mcp")

_reminders = RemindersAdapter()
_calendar = CalendarAdapter()
_contacts = ContactsAdapter()
_files = FilesAdapter()
_maps = MapsAdapter()
_mail = MailAdapter()
_notes = NotesAdapter()


def _emit(p: Pointer) -> dict[str, str]:
    return {"id": p.id, "summary": p.summary, "deeplink": p.deeplink}


def _read_only() -> bool:
    """True when APPLE_MCP_READ_ONLY is set; writes are then not registered."""
    val = os.environ.get("APPLE_MCP_READ_ONLY", "").strip().lower()
    return val in ("1", "true", "yes")


def _write_tool(fn):
    """Register a destructive tool — skipped in read-only mode (safe-deploy guard)."""
    return fn if _read_only() else mcp.tool()(fn)


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


@mcp.tool()
def reminder_lists() -> list[dict]:
    """List reminder lists as pointers (id + name); use a name to target writes."""
    return [_emit(p) for p in _reminders.get_lists()]


@mcp.tool()
def calendars() -> list[dict]:
    """List calendars as pointers (id + name); use a name to target writes."""
    return [_emit(p) for p in _calendar.get_calendars()]


@mcp.tool()
def contacts(name: str) -> list[dict]:
    """Find contacts by name (substring). Returns pointers (id + name/org)."""
    return [_emit(p) for p in _contacts.get_pointers(name)]


@mcp.tool()
def files(name: str) -> list[dict]:
    """Find files by name via Spotlight. Returns pointers (path + filename)."""
    return [_emit(p) for p in _files.get_pointers(name)]


@mcp.tool()
def maps_open(query: str) -> dict:
    """Open Maps to a search (place or address). Maps has no readable API; open-only."""
    return {"opened": _maps.open_search(query)}


@mcp.tool()
def mail(subject: str) -> list[dict]:
    """Search the Mail inbox by subject substring. Pointers (id + subject/sender)."""
    return [_emit(p) for p in _mail.get_pointers(subject)]


@mcp.tool()
def notes(title: str) -> list[dict]:
    """Search Notes by title substring. Returns pointers (id + title)."""
    return [_emit(p) for p in _notes.get_pointers(title)]


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


@_write_tool
def create_reminder(
    title: str,
    due: str | None = None,
    list_name: str | None = None,
    notes: str | None = None,
) -> dict:
    """Create a reminder. `due` is an ISO datetime string (e.g. 2026-06-23T18:00:00)."""
    data = ReminderData(title=title, due=_parse(due), list_name=list_name, notes=notes)
    return _emit(_reminders.create_reminder(data))


@_write_tool
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


@_write_tool
def complete_reminder(id: str) -> dict:
    """Mark a reminder complete by id."""
    return _emit(_reminders.complete_reminder(id))


@_write_tool
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


@_write_tool
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


@_write_tool
def delete_event(id: str) -> dict:
    """Delete a calendar event by id."""
    _calendar.delete_event(id)
    return {"deleted": id}


@_write_tool
def create_contact(
    given_name: str,
    family_name: str | None = None,
    organization: str | None = None,
) -> dict:
    """Create a contact (given/family name + organization)."""
    data = ContactData(
        given_name=given_name, family_name=family_name, organization=organization
    )
    return _emit(_contacts.create_contact(data))


def main() -> None:
    """Console entry point (`apple-mcp`) and `python -m apple_mcp`."""
    from .runtime import bootstrap

    bootstrap()
    mcp.run()  # stdio transport
