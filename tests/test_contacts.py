"""Unit tests for the contacts adapter — pure parsing helpers (no osascript)."""

from __future__ import annotations

from apple_mcp.adapters.contacts import _deeplink, _parse, _summary
from apple_mcp.contracts import Pointer


def test_summary_name_and_org():
    assert _summary("Jane Doe", "Acme") == "Jane Doe — Acme"


def test_summary_name_only():
    assert _summary("Jane Doe", "") == "Jane Doe"


def test_summary_org_only():
    assert _summary("", "Acme") == "Acme"


def test_summary_empty_is_placeholder():
    assert _summary("  ", "  ") == "(unnamed contact)"


def test_deeplink_scheme():
    assert _deeplink("X:ABPerson") == "addressbook://X:ABPerson"


def test_parse_tab_lines():
    raw = "C-1\tJane Doe\tAcme\nC-2\tBob\t\n"
    ptrs = _parse(raw)
    assert len(ptrs) == 2
    assert isinstance(ptrs[0], Pointer)
    assert ptrs[0].id == "C-1" and ptrs[0].summary == "Jane Doe — Acme"
    assert ptrs[0].deeplink == "addressbook://C-1"
    assert ptrs[1].id == "C-2" and ptrs[1].summary == "Bob"


def test_parse_skips_blank_lines():
    assert _parse("\n   \n") == []
