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


def test_summary_with_phone_and_email():
    s = _summary("Jane Doe", "Acme", "+3212345", "jane@acme.com")
    assert s == "Jane Doe — Acme · +3212345 · jane@acme.com"


def test_summary_phone_only_no_org():
    assert _summary("Bob", "", "+15550100", "") == "Bob · +15550100"


def test_summary_email_only_no_name():
    assert _summary("", "", "", "x@y.com") == "x@y.com"


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


def test_parse_five_field_line_with_phone_email():
    raw = "C-1\tJane Doe\tAcme\t+3212345\tjane@acme.com\n"
    ptrs = _parse(raw)
    assert ptrs[0].id == "C-1"
    assert ptrs[0].summary == "Jane Doe — Acme · +3212345 · jane@acme.com"


def test_parse_three_field_line_still_works():
    # back-compat: a person with no phone/email yields the old name—org summary
    ptrs = _parse("C-2\tBob\tAcme\n")
    assert ptrs[0].summary == "Bob — Acme"


def test_parse_skips_blank_lines():
    assert _parse("\n   \n") == []
