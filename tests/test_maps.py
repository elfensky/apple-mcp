"""Unit tests for the maps adapter — pure URL construction (no `open` subprocess)."""

from __future__ import annotations

import pytest

from apple_mcp.adapters.maps import _maps_url


def test_maps_url_encodes():
    assert _maps_url("Eiffel Tower") == "maps://?q=Eiffel%20Tower"


def test_maps_url_strips():
    assert _maps_url("  Paris  ") == "maps://?q=Paris"


def test_maps_url_empty_raises():
    with pytest.raises(ValueError, match="maps needs a query"):
        _maps_url("   ")
