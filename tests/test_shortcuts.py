"""Unit tests for the shortcuts adapter — pure mapping/filtering (no CLI)."""

from __future__ import annotations

from apple_mcp.adapters.shortcuts import MAX_SHORTCUTS, _filter_names, _pointer
from apple_mcp.contracts import Pointer


def test_pointer():
    p = _pointer("Track water")
    assert isinstance(p, Pointer)
    assert p.id == "Track water" and p.summary == "Track water" and p.deeplink == ""


def test_filter_substring_case_insensitive():
    names = ["Driving Mode", "Track water", "Open with Opener"]
    assert _filter_names(names, "track") == ["Track water"]


def test_filter_empty_returns_all():
    assert _filter_names(["a", "b"], "  ") == ["a", "b"]


def test_filter_caps_at_max():
    big = [str(i) for i in range(MAX_SHORTCUTS + 10)]
    assert len(_filter_names(big, "")) == MAX_SHORTCUTS
