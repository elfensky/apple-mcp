"""Unit tests for the mail adapter — pure parsing helpers (no osascript)."""

from __future__ import annotations

from apple_mcp.adapters.mail import _deeplink, _parse, _summary
from apple_mcp.contracts import Pointer


def test_summary_subject_and_sender():
    assert _summary("Invoice", "Bob <bob@x.com>") == "Invoice — Bob <bob@x.com>"


def test_summary_subject_only():
    assert _summary("Invoice", "") == "Invoice"


def test_summary_empty_is_placeholder():
    assert _summary("  ", "  ") == "(no subject)"


def test_deeplink_wraps_message_id():
    assert _deeplink("abc@host") == "message://%3cabc@host%3e"


def test_deeplink_strips_existing_brackets():
    assert _deeplink("<abc@host>") == "message://%3cabc@host%3e"


def test_parse_tab_lines():
    raw = "abc@host\tInvoice\tBob\n<def@host>\tHello\t\n"
    ptrs = _parse(raw)
    assert len(ptrs) == 2
    assert isinstance(ptrs[0], Pointer)
    assert ptrs[0].id == "abc@host" and ptrs[0].summary == "Invoice — Bob"
    assert ptrs[0].deeplink == "message://%3cabc@host%3e"
    assert ptrs[1].summary == "Hello"


def test_parse_skips_blank():
    assert _parse("\n  \n") == []
