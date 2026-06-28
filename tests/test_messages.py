"""Unit tests for the messages adapter — pure parsing (no osascript)."""

from __future__ import annotations

from mac_mcp.adapters.messages import _parse
from mac_mcp.contracts import Pointer


def test_parse_guid_and_name():
    ptrs = _parse("guid-1\tFamily\nguid-2\t\n")
    assert len(ptrs) == 2
    assert isinstance(ptrs[0], Pointer)
    assert ptrs[0].id == "guid-1" and ptrs[0].summary == "Family"
    assert ptrs[0].deeplink == ""
    assert ptrs[1].summary == "(chat)"  # unnamed 1:1 chat


def test_parse_skips_blank():
    assert _parse("\n  \n") == []
