"""Unit tests for the shortcuts adapter — pure mapping/filtering + run dispatch.

The mapping/filter helpers run with no CLI; ``run_shortcut`` is tested by faking
``subprocess.run`` at the module boundary (no real shortcut executed).
"""

from __future__ import annotations

import subprocess

import pytest

from apple_mcp.adapters.shortcuts import (
    MAX_OUTPUT,
    MAX_SHORTCUTS,
    ShortcutsAdapter,
    _filter_names,
    _pointer,
    _run_pointer,
)
from apple_mcp.contracts import Pointer


def _fake_run(monkeypatch, *, returncode=0, stdout="", stderr=""):
    """Swap shortcuts.subprocess.run for a fake; return a dict capturing the call."""
    seen: dict = {}

    def fake(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    monkeypatch.setattr("apple_mcp.adapters.shortcuts.subprocess.run", fake)
    return seen


def test_pointer():
    p = _pointer("Track water")
    assert isinstance(p, Pointer)
    assert p.id == "Track water" and p.summary == "Track water" and p.deeplink == ""


def test_filter_substring_case_insensitive():
    names = ["Driving Mode", "Track water", "Open with Opener"]
    assert _filter_names(names, "track") == ["Track water"]


def test_filter_empty_returns_all():
    assert _filter_names(["a", "b"], "  ") == ["a", "b"]


def test_filter_caps_at_max():
    big = [str(i) for i in range(MAX_SHORTCUTS + 10)]
    assert len(_filter_names(big, "")) == MAX_SHORTCUTS


def test_run_pointer_no_output():
    p = _run_pointer("Driving Mode", "")
    assert p.id == "Driving Mode"
    assert p.summary == "ran Driving Mode" and p.deeplink == ""


def test_run_pointer_with_output():
    assert _run_pointer("Weather", "  72F sunny  ").summary == "ran Weather → 72F sunny"


def test_run_pointer_truncates_long_output():
    p = _run_pointer("Dump", "x" * (MAX_OUTPUT + 50))
    assert p.summary.endswith("…")
    assert len(p.summary) <= len("ran Dump → ") + MAX_OUTPUT + 1


def test_run_shortcut_decodes_leniently(monkeypatch):
    # the hardening: a non-text stdout must never crash the decode
    seen = _fake_run(monkeypatch, stdout="ok")
    p = ShortcutsAdapter().run_shortcut("Weather")
    assert seen["kw"].get("errors") == "replace"
    assert "--output-path" in seen["cmd"] and "--input-path" not in seen["cmd"]
    assert p.summary == "ran Weather → ok"


def test_run_shortcut_pipes_input(monkeypatch):
    seen = _fake_run(monkeypatch, stdout="done")
    ShortcutsAdapter().run_shortcut("Append Note", "hello")
    assert "--input-path" in seen["cmd"] and seen["kw"].get("input") == "hello"


def test_run_shortcut_raises_on_nonzero(monkeypatch):
    _fake_run(monkeypatch, returncode=1, stderr="no such shortcut")
    with pytest.raises(RuntimeError, match="shortcuts run"):
        ShortcutsAdapter().run_shortcut("Nope")


def test_run_shortcut_rejects_empty_name(monkeypatch):
    _fake_run(monkeypatch)  # never reached — empty name fails first
    with pytest.raises(ValueError, match="needs a shortcut name"):
        ShortcutsAdapter().run_shortcut("   ")
