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

# notes_all: every note across accounts, excluding Recently Deleted. id+name read in
# one multi-property snapshot ({id, name} of (notes of f)) stay aligned — do NOT split
# into separate "id of every note" / "name of every note" events (they can mispair if
# Notes mutates between calls). Lines via `set end of` + TID join avoid O(n^2) string
# concatenation on large libraries. ponytail: no cap — 30s osascript timeout is the
# de-facto ceiling; a too-large library fails whole. Add pagination only if needed.
_LIST_ALL = """on run argv
  set theLines to {}
  tell application "Notes"
    repeat with acc in accounts
      set accName to name of acc
      repeat with f in folders of acc
        if name of f is not "Recently Deleted" then
          set {theIds, theNames} to ({id, name} of (notes of f))
          set fName to name of f
          set folder_label to accName & " / " & fName
          repeat with i from 1 to (count of theIds)
            set nId to item i of theIds
            set nName to item i of theNames
            set line to (nId & tab & folder_label & tab & nName)
            set end of theLines to line
          end repeat
        end if
      end repeat
    end repeat
  end tell
  set AppleScript's text item delimiters to linefeed
  return theLines as text
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


def _parse_all(raw: str) -> list[Pointer]:
    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        ident = parts[0]
        folder = parts[1] if len(parts) > 1 else None
        title = parts[2] if len(parts) > 2 else ""
        out.append(
            Pointer(
                id=ident,
                summary=title.strip() or "(untitled note)",
                deeplink="",
                folder=folder,
            )
        )
    return out


class NotesAdapter:
    def get_pointers(self, query: str) -> list[Pointer]:
        """query: a title substring to find."""
        q = query.strip()
        if not q:
            raise ValueError("notes read needs a title substring (got an empty query)")
        return _parse(run_osascript(_SEARCH, q))[:MAX_NOTES]

    def get_all(self) -> list[Pointer]:
        """Every note (excludes Recently Deleted) as account-qualified pointers.

        Folder is "Account / Folder". No cap: a very large library can exceed the
        osascript 30s timeout, in which case the whole call fails (no partial results).
        """
        return _parse_all(run_osascript(_LIST_ALL))
