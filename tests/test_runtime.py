"""Unit tests for the native runtime — pure helpers only; no EventKit calls."""
from __future__ import annotations

import pytest

from apple_mcp.runtime import AccessDenied, _decide


def test_decide_passes_on_full_access():
    _decide(3)  # EKAuthorizationStatusFullAccess — returns without raising


@pytest.mark.parametrize("status", [0, 1, 2, 4])  # notDetermined, restricted, denied, writeOnly
def test_decide_raises_on_anything_else(status):
    with pytest.raises(AccessDenied, match="System Settings"):
        _decide(status)


from datetime import datetime

from apple_mcp.runtime import due_components, from_nsdate, run_native, store, to_nsdate


def test_store_rejects_off_worker_calls():
    # Called directly (main thread, not the apple-native worker) → must refuse.
    import pytest
    with pytest.raises(RuntimeError, match="run_native"):
        store()


def test_store_returns_same_instance_on_worker():
    s1 = run_native(store)
    s2 = run_native(store)
    assert s1 is s2  # one store, created once, on the worker


def test_nsdate_roundtrip():
    dt = datetime(2026, 6, 23, 9, 30, 0)
    assert abs((from_nsdate(to_nsdate(dt)) - dt).total_seconds()) < 1


def test_due_components_fields():
    c = due_components(datetime(2026, 6, 23, 18, 45))
    assert (c.year(), c.month(), c.day(), c.hour(), c.minute()) == (2026, 6, 23, 18, 45)
