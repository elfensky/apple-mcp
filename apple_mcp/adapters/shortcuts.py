"""Shortcuts adapter — the ``shortcuts`` CLI (#22). No app, no Automation prompt.

``shortcuts list`` enumerates the user's shortcuts; an optional query filters by name.
``Pointer.id``/``summary`` are the shortcut name; ``deeplink`` empty (the name is the
handle — run via the Shortcuts CLI if a run tool is ever added). Read-only.
"""

from __future__ import annotations

import subprocess

from ..contracts import Pointer

MAX_SHORTCUTS = 100
_TIMEOUT = 10.0


def _pointer(name: str) -> Pointer:
    return Pointer(id=name, summary=name, deeplink="")


def _filter_names(names: list[str], query: str) -> list[str]:
    q = query.strip().lower()
    if q:
        names = [n for n in names if q in n.lower()]
    return names[:MAX_SHORTCUTS]


class ShortcutsAdapter:
    def get_pointers(self, query: str = "") -> list[Pointer]:
        """query: optional name substring (empty lists all shortcuts)."""
        proc = subprocess.run(
            ["shortcuts", "list"], capture_output=True, text=True, timeout=_TIMEOUT
        )
        if proc.returncode != 0:
            raise RuntimeError(f"shortcuts list failed: {proc.stderr.strip()}")
        names = [n for n in proc.stdout.splitlines() if n.strip()]
        return [_pointer(n) for n in _filter_names(names, query)]
