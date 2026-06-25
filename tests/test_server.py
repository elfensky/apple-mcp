"""Server tool tests — tools are thin dispatch; we swap fake adapters at the
boundary (no EventKit)."""

from __future__ import annotations

from datetime import datetime

import pytest

import apple_mcp.server as srv
from apple_mcp.contracts import CalendarEventData, ContactData, Pointer, ReminderData


class _FakeSource:
    def __init__(self):
        self.queries: list[str] = []
        self.enumerated = 0

    def get_pointers(self, query: str) -> list[Pointer]:
        self.queries.append(query)
        return [Pointer(id="P-1", summary="s", deeplink="d")]

    def get_lists(self) -> list[Pointer]:
        self.enumerated += 1
        return [Pointer(id="L-1", summary="Home", deeplink="")]

    def get_calendars(self) -> list[Pointer]:
        self.enumerated += 1
        return [Pointer(id="C-1", summary="Work", deeplink="")]


def test_server_constructs():
    assert srv.mcp is not None


def test_reminders_tool_dispatches(monkeypatch):
    fake = _FakeSource()
    monkeypatch.setattr(srv, "_reminders", fake)
    out = srv.reminders("overdue")
    assert fake.queries == ["overdue"]
    assert out == [{"id": "P-1", "summary": "s", "deeplink": "d"}]


def test_events_tool_dispatches(monkeypatch):
    fake = _FakeSource()
    monkeypatch.setattr(srv, "_calendar", fake)
    out = srv.events("week")
    assert fake.queries == ["week"]
    assert out[0]["id"] == "P-1"


def test_contacts_tool_dispatches(monkeypatch):
    fake = _FakeSource()
    monkeypatch.setattr(srv, "_contacts", fake)
    out = srv.contacts("jane")
    assert fake.queries == ["jane"]
    assert out == [{"id": "P-1", "summary": "s", "deeplink": "d"}]


def test_reminder_lists_tool_dispatches(monkeypatch):
    fake = _FakeSource()
    monkeypatch.setattr(srv, "_reminders", fake)
    out = srv.reminder_lists()
    assert fake.enumerated == 1
    assert out == [{"id": "L-1", "summary": "Home", "deeplink": ""}]


def test_calendars_tool_dispatches(monkeypatch):
    fake = _FakeSource()
    monkeypatch.setattr(srv, "_calendar", fake)
    out = srv.calendars()
    assert fake.enumerated == 1
    assert out == [{"id": "C-1", "summary": "Work", "deeplink": ""}]


class _FakeWriter:
    def __init__(self):
        self.calls: list = []

    def create_reminder(self, data: ReminderData) -> Pointer:
        self.calls.append(("create_reminder", data))
        return Pointer(id="R-9", summary="s", deeplink="d")

    def update_reminder(self, ident: str, data: ReminderData) -> Pointer:
        self.calls.append(("update_reminder", ident, data))
        return Pointer(id=ident, summary="s", deeplink="d")

    def complete_reminder(self, ident: str) -> Pointer:
        self.calls.append(("complete_reminder", ident))
        return Pointer(id=ident, summary="done", deeplink="d")

    def create_event(self, data: CalendarEventData) -> Pointer:
        self.calls.append(("create_event", data))
        return Pointer(id="E-9", summary="s", deeplink="d")

    def update_event(self, ident: str, data: CalendarEventData) -> Pointer:
        self.calls.append(("update_event", ident, data))
        return Pointer(id=ident, summary="s", deeplink="d")

    def delete_event(self, ident: str) -> None:
        self.calls.append(("delete_event", ident))

    def create_contact(self, data: ContactData) -> Pointer:
        self.calls.append(("create_contact", data))
        return Pointer(id="C-9", summary="s", deeplink="d")


def test_create_reminder_builds_typed_payload(monkeypatch):
    fake = _FakeWriter()
    monkeypatch.setattr(srv, "_reminders", fake)
    out = srv.create_reminder(
        "Call dentist", due="2026-06-23T18:00:00", list_name="Home"
    )
    kind, data = fake.calls[0]
    assert kind == "create_reminder"
    assert data == ReminderData(
        title="Call dentist",
        due=datetime(2026, 6, 23, 18, 0),
        list_name="Home",
        notes=None,
    )
    assert out == {"id": "R-9", "summary": "s", "deeplink": "d"}


def test_update_reminder_builds_typed_payload(monkeypatch):
    fake = _FakeWriter()
    monkeypatch.setattr(srv, "_reminders", fake)
    out = srv.update_reminder(
        "R-1", "Call dentist", due="2026-06-23T18:00:00", list_name="Home"
    )
    kind, ident, data = fake.calls[0]
    assert kind == "update_reminder" and ident == "R-1"
    assert data == ReminderData(
        title="Call dentist",
        due=datetime(2026, 6, 23, 18, 0),
        list_name="Home",
        notes=None,
    )
    assert out == {"id": "R-1", "summary": "s", "deeplink": "d"}


def test_complete_reminder_dispatches(monkeypatch):
    fake = _FakeWriter()
    monkeypatch.setattr(srv, "_reminders", fake)
    out = srv.complete_reminder("R-1")
    assert fake.calls[0] == ("complete_reminder", "R-1") and out["id"] == "R-1"


def test_create_event_builds_typed_payload(monkeypatch):
    fake = _FakeWriter()
    monkeypatch.setattr(srv, "_calendar", fake)
    srv.create_event("Standup", start="2026-06-24T09:00:00", end="2026-06-24T09:15:00")
    kind, data = fake.calls[0]
    assert kind == "create_event"
    assert data == CalendarEventData(
        title="Standup",
        start=datetime(2026, 6, 24, 9, 0),
        end=datetime(2026, 6, 24, 9, 15),
    )


def test_update_event_builds_typed_payload(monkeypatch):
    fake = _FakeWriter()
    monkeypatch.setattr(srv, "_calendar", fake)
    out = srv.update_event(
        "E-1", "Standup", start="2026-06-24T09:00:00", end="2026-06-24T09:15:00"
    )
    kind, ident, data = fake.calls[0]
    assert kind == "update_event" and ident == "E-1"
    assert data == CalendarEventData(
        title="Standup",
        start=datetime(2026, 6, 24, 9, 0),
        end=datetime(2026, 6, 24, 9, 15),
    )
    assert out == {"id": "E-1", "summary": "s", "deeplink": "d"}


def test_delete_event_dispatches(monkeypatch):
    fake = _FakeWriter()
    monkeypatch.setattr(srv, "_calendar", fake)
    out = srv.delete_event("E-1")
    assert fake.calls[0] == ("delete_event", "E-1") and out == {"deleted": "E-1"}


def test_create_contact_builds_typed_payload(monkeypatch):
    fake = _FakeWriter()
    monkeypatch.setattr(srv, "_contacts", fake)
    out = srv.create_contact("Jane", family_name="Doe", organization="Acme")
    kind, data = fake.calls[0]
    assert kind == "create_contact"
    assert data == ContactData(
        given_name="Jane", family_name="Doe", organization="Acme"
    )
    assert out == {"id": "C-9", "summary": "s", "deeplink": "d"}


def test_create_event_rejects_empty_start():
    # Required event dates fail clearly at the tool boundary, not as an obscure
    # worker-thread crash.
    with pytest.raises(ValueError, match="ISO datetime"):
        srv.create_event("Standup", start="", end="2026-06-24T09:15:00")


@pytest.mark.parametrize("val", ["1", "true", "TRUE", "yes", "Yes"])
def test_read_only_truthy(monkeypatch, val):
    monkeypatch.setenv("APPLE_MCP_READ_ONLY", val)
    assert srv._read_only() is True


@pytest.mark.parametrize("val", ["", "0", "no", "false", "off"])
def test_read_only_falsy(monkeypatch, val):
    monkeypatch.setenv("APPLE_MCP_READ_ONLY", val)
    assert srv._read_only() is False


def test_read_only_unset_is_false(monkeypatch):
    monkeypatch.delenv("APPLE_MCP_READ_ONLY", raising=False)
    assert srv._read_only() is False
