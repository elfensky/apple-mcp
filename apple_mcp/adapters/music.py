"""Music adapter — Music.app via osascript (Automation TCC). Read-only: track search.

Searches library tracks whose name contains the query. ``Pointer.id`` is the track's
``database ID``; ``summary`` is name + artist; ``deeplink`` is empty (no verified per-
track URL scheme). Pointers, not media. Capped + osascript-timeout-bounded (Music's
AppleScript is slow on large libraries); user input goes via argv (no injection).
"""

from __future__ import annotations

from ..contracts import Pointer
from ..runtime import run_osascript

MAX_TRACKS = 25

_SEARCH = """on run argv
  set q to item 1 of argv
  set out to ""
  tell application "Music"
    repeat with t in (tracks whose name contains q)
      set out to out & (database ID of t) & tab
      set out to out & (name of t) & tab & (artist of t) & linefeed
    end repeat
  end tell
  return out
end run"""


def _summary(name: str, artist: str) -> str:
    name, artist = name.strip(), artist.strip()
    if name and artist:
        return f"{name} — {artist}"
    return name or artist or "(unknown track)"


def _parse(raw: str) -> list[Pointer]:
    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        tid = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        artist = parts[2] if len(parts) > 2 else ""
        out.append(Pointer(id=tid, summary=_summary(name, artist), deeplink=""))
    return out


class MusicAdapter:
    def get_pointers(self, query: str) -> list[Pointer]:
        """query: a track-name substring to find in the library."""
        q = query.strip()
        if not q:
            raise ValueError("music read needs a track-name substring (empty query)")
        return _parse(run_osascript(_SEARCH, q))[:MAX_TRACKS]
