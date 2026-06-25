"""Unit tests for the files adapter — pure mapping (no mdfind subprocess)."""

from __future__ import annotations

from apple_mcp.adapters.files import _file_pointer
from apple_mcp.contracts import Pointer


def test_file_pointer():
    p = _file_pointer("/Users/x/Developer/apple-mcp/pyproject.toml")
    assert isinstance(p, Pointer)
    assert p.id == "/Users/x/Developer/apple-mcp/pyproject.toml"
    assert p.summary == "pyproject.toml"
    assert p.deeplink == "file:///Users/x/Developer/apple-mcp/pyproject.toml"


def test_file_pointer_no_slash():
    p = _file_pointer("README.md")
    assert p.id == "README.md" and p.summary == "README.md"
