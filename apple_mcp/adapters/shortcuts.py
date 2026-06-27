"""Shortcuts adapter — the ``shortcuts`` CLI (#22). No app, no Automation prompt.

``shortcuts list`` enumerates the user's shortcuts; an optional query filters by name.
``Pointer.id``/``summary`` are the shortcut name; ``deeplink`` empty (the name is the
handle). ``run_shortcut`` invokes one by name (``shortcuts run``) — the one write, a
gateway to every automation the user owns.
"""

from __future__ import annotations

import subprocess

from ..contracts import Pointer

MAX_SHORTCUTS = 100
MAX_OUTPUT = 280  # pointers-not-payload: cite the run + a bounded snippet of any output
_TIMEOUT = 10.0
_RUN_TIMEOUT = 30.0  # a shortcut does real work — longer than `list`


def _pointer(name: str) -> Pointer:
    return Pointer(id=name, summary=name, deeplink="")


def _run_pointer(name: str, output: str) -> Pointer:
    """Cite that a shortcut ran, plus a bounded snippet of any stdout it returned."""
    out = output.strip()
    summary = f"ran {name}"
    if out:
        snippet = out if len(out) <= MAX_OUTPUT else out[:MAX_OUTPUT] + "…"
        summary = f"{summary} → {snippet}"
    return Pointer(id=name, summary=summary, deeplink="")


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

    def run_shortcut(self, name: str, input_text: str | None = None) -> Pointer:
        """Run a shortcut by exact name; optional text ``input_text`` piped via stdin.

        ``--output-path -`` captures any result on stdout (best-effort; some shortcuts
        return nothing). The Pointer cites the run + a truncated snippet, never a full
        payload.
        """
        name = name.strip()
        if not name:
            raise ValueError("run_shortcut needs a shortcut name (got an empty name)")
        cmd = ["shortcuts", "run", name, "--output-path", "-"]
        if input_text is not None:
            cmd += ["--input-path", "-"]
        # errors="replace": a shortcut may return non-text (an image/file) on stdout via
        # --output-path -; a strict UTF-8 decode would crash the worker. Degrade to a
        # lossy snippet instead — it's truncated to MAX_OUTPUT anyway.
        proc = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=_RUN_TIMEOUT,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"shortcuts run {name!r} failed: {proc.stderr.strip()}")
        return _run_pointer(name, proc.stdout)
