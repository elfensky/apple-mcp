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
from .adapters.mail import MailAdapter
from .adapters.messages import MessagesAdapter
from .adapters.notes import NotesAdapter
from .adapters.photos import PhotosAdapter
from .adapters.reminders import RemindersAdapter
from .adapters.safari import SafariAdapter
from .adapters.shortcuts import ShortcutsAdapter
from .contracts import CalendarEventData, ContactData, Pointer, ReminderData

mcp = FastMCP("apple-mcp")

_reminders = RemindersAdapter()
_calendar = CalendarAdapter()
_contacts = ContactsAdapter()
_mail = MailAdapter()
_notes = NotesAdapter()
_safari = SafariAdapter()
_photos = PhotosAdapter()
_messages = MessagesAdapter()
_shortcuts = ShortcutsAdapter()


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
def mail(subject: str) -> list[dict]:
    """Search the Mail inbox by subject substring. Pointers (id + subject/sender)."""
    return [_emit(p) for p in _mail.get_pointers(subject)]


@mcp.tool()
def notes(title: str) -> list[dict]:
    """Search Notes by title substring. Returns pointers (id + title)."""
    return [_emit(p) for p in _notes.get_pointers(title)]


@mcp.tool()
def safari_tabs() -> list[dict]:
    """List open Safari tabs as pointers (url + title)."""
    return [_emit(p) for p in _safari.get_tabs()]


@mcp.tool()
def photos(query: str) -> list[dict]:
    """Search Photos (filename, place, date). Returns pointers (id + filename)."""
    return [_emit(p) for p in _photos.get_pointers(query)]


@mcp.tool()
def messages_chats() -> list[dict]:
    """List Messages conversations (id + name). No content; sending isn't supported."""
    return [_emit(p) for p in _messages.get_chats()]


@mcp.tool()
def shortcuts(name: str = "") -> list[dict]:
    """List/search Shortcuts by name (empty lists all). Pointers (name)."""
    return [_emit(p) for p in _shortcuts.get_pointers(name)]


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


def _priority(n: int) -> int:
    """EventKit reminder priority: 0 (none) or 1–9 (1 highest). Reject out-of-range."""
    if not 0 <= n <= 9:
        raise ValueError(f"priority must be 0–9 (0=none, 1=highest), got {n}")
    return n


@_write_tool
def create_reminder(
    title: str,
    due: str | None = None,
    list_name: str | None = None,
    notes: str | None = None,
    priority: int = 0,
    start: str | None = None,
) -> dict:
    """Create a reminder. `due`/`start` are ISO datetimes; `priority` 0–9 (0=none)."""
    data = ReminderData(
        title=title,
        due=_parse(due),
        list_name=list_name,
        notes=notes,
        priority=_priority(priority),
        start=_parse(start),
    )
    return _emit(_reminders.create_reminder(data))


@_write_tool
def update_reminder(
    id: str,
    title: str,
    due: str | None = None,
    list_name: str | None = None,
    notes: str | None = None,
    priority: int = 0,
    start: str | None = None,
) -> dict:
    """Update a reminder by id (full replace from the given fields)."""
    data = ReminderData(
        title=title,
        due=_parse(due),
        list_name=list_name,
        notes=notes,
        priority=_priority(priority),
        start=_parse(start),
    )
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
    all_day: bool = False,
) -> dict:
    """Create a calendar event. `start`/`end` are ISO datetime strings; `all_day` makes
    it all-day."""
    data = CalendarEventData(
        title=title,
        start=_parse_required("start", start),
        end=_parse_required("end", end),
        calendar=calendar,
        location=location,
        notes=notes,
        all_day=all_day,
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
    all_day: bool = False,
) -> dict:
    """Update an event by id (full replace from the given fields)."""
    data = CalendarEventData(
        title=title,
        start=_parse_required("start", start),
        end=_parse_required("end", end),
        calendar=calendar,
        location=location,
        notes=notes,
        all_day=all_day,
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


@_write_tool
def run_shortcut(name: str, input: str | None = None) -> dict:
    """Run a Shortcut by name; optional text `input`. Returns a pointer."""
    return _emit(_shortcuts.run_shortcut(name, input))


@_write_tool
def safari_open(url: str) -> dict:
    """Open a URL in a new Safari tab; adds https:// if no scheme."""
    return _emit(_safari.open_url(url))


def main() -> None:
    """Console entry point (`apple-mcp`) and `python -m apple_mcp`."""
    from .runtime import bootstrap

    bootstrap()
    mcp.run()  # stdio transport
