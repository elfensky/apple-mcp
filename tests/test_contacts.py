"""Unit tests for the contacts adapter — pure mapping helpers (no CNContactStore)."""

from __future__ import annotations

from types import SimpleNamespace

from apple_mcp.adapters.contacts import (
    _contact_deeplink,
    _contact_pointer,
    _contact_summary,
)
from apple_mcp.contracts import Pointer


def _fake(given="", family="", org="", ident="C-1"):
    return SimpleNamespace(
        givenName=lambda: given,
        familyName=lambda: family,
        organizationName=lambda: org,
        identifier=lambda: ident,
    )


def test_summary_name_and_org():
    assert _contact_summary(_fake("Jane", "Doe", "Acme")) == "Jane Doe — Acme"


def test_summary_name_only():
    assert _contact_summary(_fake("Jane", "Doe")) == "Jane Doe"


def test_summary_org_only():
    assert _contact_summary(_fake(org="Acme")) == "Acme"


def test_summary_empty_is_placeholder():
    assert _contact_summary(_fake()) == "(unnamed contact)"


def test_deeplink_scheme():
    assert _contact_deeplink("C-9") == "addressbook://C-9"


def test_pointer_shape():
    p = _contact_pointer(_fake("Jane", "Doe", "Acme", "C-9"))
    assert isinstance(p, Pointer)
    assert p.id == "C-9" and p.summary == "Jane Doe — Acme"
    assert p.deeplink == "addressbook://C-9"
