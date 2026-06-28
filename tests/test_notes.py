"""Unit tests for the notes adapter — pure parsing (no osascript)."""

from __future__ import annotations

from apple_mcp.adapters.notes import _parse, _parse_all
from apple_mcp.contracts import Pointer


def test_parse_id_and_title():
    raw = "x-coredata://S/ICNote/p1\tGroceries\nx-coredata://S/ICNote/p2\tIdeas\n"
    ptrs = _parse(raw)
    assert len(ptrs) == 2
    assert isinstance(ptrs[0], Pointer)
    assert ptrs[0].id == "x-coredata://S/ICNote/p1"
    assert ptrs[0].summary == "Groceries"
    assert ptrs[0].deeplink == ""
    assert ptrs[1].summary == "Ideas"


def test_parse_untitled():
    ptrs = _parse("x-coredata://S/ICNote/p3\t\n")
    assert ptrs[0].summary == "(untitled note)"


def test_parse_skips_blank():
    assert _parse("\n   \n") == []


def test_parse_all_id_folder_title():
    raw = (
        "x-coredata://S/ICNote/p1\tiCloud / Groceries\tMilk\n"
        "x-coredata://S/ICNote/p2\tOn My Mac / Ideas\tRocket\n"
    )
    ptrs = _parse_all(raw)
    assert len(ptrs) == 2
    assert ptrs[0].id == "x-coredata://S/ICNote/p1"
    assert ptrs[0].folder == "iCloud / Groceries"
    assert ptrs[0].summary == "Milk"
    assert ptrs[0].deeplink == ""
    assert ptrs[1].folder == "On My Mac / Ideas"


def test_parse_all_untitled():
    ptrs = _parse_all("x-coredata://S/ICNote/p3\tiCloud / Notes\t\n")
    assert ptrs[0].summary == "(untitled note)"
    assert ptrs[0].folder == "iCloud / Notes"


def test_parse_all_skips_blank():
    assert _parse_all("\n   \n") == []
