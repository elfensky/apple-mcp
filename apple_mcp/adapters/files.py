"""Files adapter — Spotlight name search via ``mdfind`` (#16).

Not an app and not osascript: ``mdfind`` is a plain system binary that queries the
Spotlight index, so there's no Automation prompt and no usage-description bundle needed.
Returns Pointers (id = absolute path, deeplink = ``file://``) — pointers, not contents.
"""

from __future__ import annotations

import subprocess

from ..contracts import Pointer

MAX_FILES = 50  # cap a broad name match
_TIMEOUT = 15.0  # seconds — Spotlight queries are fast; bound a pathological one


def _file_pointer(path: str) -> Pointer:
    name = path.rsplit("/", 1)[-1] or path
    return Pointer(id=path, summary=name, deeplink=f"file://{path}")


class FilesAdapter:
    def get_pointers(self, query: str) -> list[Pointer]:
        """query: a filename substring to find via Spotlight (``mdfind -name``)."""
        q = query.strip()
        if not q:
            raise ValueError("files read needs a name to search (got an empty query)")
        proc = subprocess.run(
            ["mdfind", "-name", q],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"mdfind failed: {proc.stderr.strip()}")
        paths = [p for p in proc.stdout.splitlines() if p.strip()]
        return [_file_pointer(p) for p in paths[:MAX_FILES]]
