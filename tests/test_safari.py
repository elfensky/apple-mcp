"""Unit tests for the safari adapter — pure parsing (no osascript)."""

from __future__ import annotations

import pytest

from apple_mcp.adapters.safari import _normalize_url, _parse
from apple_mcp.contracts import Pointer


def test_parse_url_and_title():
    raw = "https://x.com/a\tPage A\nhttps://y.com/\t\n"
    ptrs = _parse(raw)
    assert len(ptrs) == 2
    assert isinstance(ptrs[0], Pointer)
    assert ptrs[0].id == "https://x.com/a" and ptrs[0].summary == "Page A"
    assert ptrs[0].deeplink == "https://x.com/a"
    # empty title falls back to the URL
    assert ptrs[1].summary == "https://y.com/"


def test_parse_skips_blank():
    assert _parse("\n  \n") == []


def test_normalize_url_adds_scheme():
    assert _normalize_url("example.com") == "https://example.com"


def test_normalize_url_keeps_existing_scheme():
    assert _normalize_url("  http://x.com/a  ") == "http://x.com/a"


def test_normalize_url_empty_raises():
    with pytest.raises(ValueError, match="needs a URL"):
        _normalize_url("   ")
