"""Server tool tests — tools are thin dispatch; we swap fake adapters at the boundary (no EventKit)."""
from __future__ import annotations

import apple_mcp.server as srv
from apple_mcp.contracts import Pointer


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
