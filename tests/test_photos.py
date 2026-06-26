"""Unit tests for the photos adapter — pure parsing (no osascript)."""

from __future__ import annotations

from apple_mcp.adapters.photos import _parse
from apple_mcp.contracts import Pointer


def test_parse_id_and_filename():
    ptrs = _parse("ABC123\tIMG_0001.jpg\nDEF456\t\n")
    assert len(ptrs) == 2
    assert isinstance(ptrs[0], Pointer)
    assert ptrs[0].id == "ABC123" and ptrs[0].summary == "IMG_0001.jpg"
    assert ptrs[0].deeplink == ""
    assert ptrs[1].summary == "(photo)"


def test_parse_skips_blank():
    assert _parse("\n  \n") == []
