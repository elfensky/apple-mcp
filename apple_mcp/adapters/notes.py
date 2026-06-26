"""Notes adapter — Notes.app via osascript (Automation TCC). Read-only v1: title search.

Notes is scriptable. ``get_pointers(query)`` searches notes whose name (title) contains
the query. ``Pointer.id`` is the note's ``x-coredata://…`` id; ``summary`` is the title.
``deeplink`` is empty — Notes has no verified open-by-id URL scheme, so id + title are
the handle. Pointers, not bodies (the body is never fetched). Capped and osascript-
timeout-bounded; user input goes via argv (no script injection).
"""

from __future__ import annotations

from ..contracts import Pointer
from ..runtime import run_osascript

MAX_NOTES = 25

_SEARCH = """on run argv
  set q to item 1 of argv
  set out to ""
  tell application "Notes"
    repeat with n in (notes whose name contains q)
      set out to out & (id of n) & tab & (name of n) & linefeed
    end repeat
  end tell
  return out
end run"""


def _parse(raw: str) -> list[Pointer]:
    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        ident, _, name = line.partition("\t")
        out.append(
            Pointer(id=ident, summary=name.strip() or "(untitled note)", deeplink="")
        )
    return out


class NotesAdapter:
    def get_pointers(self, query: str) -> list[Pointer]:
        """query: a title substring to find."""
        q = query.strip()
        if not q:
            raise ValueError("notes read needs a title substring (got an empty query)")
        return _parse(run_osascript(_SEARCH, q))[:MAX_NOTES]
