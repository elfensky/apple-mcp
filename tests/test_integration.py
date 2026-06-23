"""Integration tests — REAL EventKit on this Mac. Run with: uv run pytest -m integration

Never run in CI (no macOS / TCC there). Grant Calendar + Reminders access when first prompted.
Tests create items in the DEFAULT list/calendar with an 'apple-mcp-test:' title prefix and
remove everything they create in teardown.
"""
from __future__ import annotations

import EventKit as EK
import pytest

from apple_mcp.runtime import request_access, run_native, store

TITLE_PREFIX = "apple-mcp-test:"


@pytest.fixture
def created():
    """Track (kind, id) of items a test creates; remove them all afterward."""
    items: list[tuple[str, str]] = []
    yield items

    def _cleanup():
        s = store()
        for kind, ident in items:
            obj = s.calendarItemWithIdentifier_(ident)
            if obj is None:
                continue
            if kind == "event":
                s.removeEvent_span_commit_error_(obj, EK.EKSpanThisEvent, True, None)
            else:
                s.removeReminder_commit_error_(obj, True, None)

    run_native(_cleanup)


@pytest.mark.integration
def test_request_access_grants_full():
    run_native(request_access)  # raises AccessDenied if not granted — grant when prompted
