"""Server tool tests — tools are thin dispatch; we swap fake adapters at the boundary (no EventKit)."""
from __future__ import annotations

from datetime import datetime

import pytest

import apple_mcp.server as srv
from apple_mcp.contracts import CalendarEventData, Pointer, ReminderData


class _FakeSource:
    def __init__(self):
        self.queries: list[str] = []

    def get_pointers(self, query: str) -> list[Pointer]:
        self.queries.append(query)
        return [Pointer(id="P-1", summary="s", deeplink="d")]


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


class _FakeWriter:
    def __init__(self):
        self.calls: list = []

    def create_reminder(self, data: ReminderData) -> Pointer:
        self.calls.append(("create_reminder", data))
        return Pointer(id="R-9", summary="s", deeplink="d")

    def complete_reminder(self, ident: str) -> Pointer:
        self.calls.append(("complete_reminder", ident))
        return Pointer(id=ident, summary="done", deeplink="d")

    def create_event(self, data: CalendarEventData) -> Pointer:
        self.calls.append(("create_event", data))
        return Pointer(id="E-9", summary="s", deeplink="d")

    def delete_event(self, ident: str) -> None:
        self.calls.append(("delete_event", ident))


def test_create_reminder_builds_typed_payload(monkeypatch):
    fake = _FakeWriter()
    monkeypatch.setattr(srv, "_reminders", fake)
    out = srv.create_reminder("Call dentist", due="2026-06-23T18:00:00", list_name="Home")
    kind, data = fake.calls[0]
    assert kind == "create_reminder"
    assert data == ReminderData(title="Call dentist", due=datetime(2026, 6, 23, 18, 0), list_name="Home", notes=None)
    assert out == {"id": "R-9", "summary": "s", "deeplink": "d"}


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
    assert data == CalendarEventData(title="Standup", start=datetime(2026, 6, 24, 9, 0), end=datetime(2026, 6, 24, 9, 15))


def test_delete_event_dispatches(monkeypatch):
    fake = _FakeWriter()
    monkeypatch.setattr(srv, "_calendar", fake)
    out = srv.delete_event("E-1")
    assert fake.calls[0] == ("delete_event", "E-1") and out == {"deleted": "E-1"}


def test_create_event_rejects_empty_start():
    # Required event dates fail clearly at the tool boundary, not as an obscure worker-thread crash.
    with pytest.raises(ValueError, match="ISO datetime"):
        srv.create_event("Standup", start="", end="2026-06-24T09:15:00")
