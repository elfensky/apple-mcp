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
