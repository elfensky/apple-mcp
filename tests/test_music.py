"""Unit tests for the music adapter — pure parsing (no osascript)."""

from __future__ import annotations

from apple_mcp.adapters.music import _parse, _summary
from apple_mcp.contracts import Pointer


def test_summary_name_and_artist():
    assert _summary("Yellow", "Coldplay") == "Yellow — Coldplay"


def test_summary_name_only():
    assert _summary("Yellow", "") == "Yellow"


def test_summary_empty_is_placeholder():
    assert _summary("  ", "  ") == "(unknown track)"


def test_parse_tab_lines():
    ptrs = _parse("123\tYellow\tColdplay\n456\tClocks\t\n")
    assert len(ptrs) == 2
    assert isinstance(ptrs[0], Pointer)
    assert ptrs[0].id == "123" and ptrs[0].summary == "Yellow — Coldplay"
    assert ptrs[0].deeplink == ""
    assert ptrs[1].summary == "Clocks"


def test_parse_skips_blank():
    assert _parse("\n  \n") == []
