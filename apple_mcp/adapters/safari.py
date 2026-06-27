"""Safari adapter — Safari.app via osascript (Automation TCC). List tabs + open a URL.

Lists every open tab across windows. ``Pointer.id`` and ``deeplink`` are the tab URL;
``summary`` is the page title. ``open_url`` opens a URL in a new tab. User input goes
via argv (no injection). Pointers, not page content.
"""

from __future__ import annotations

from ..contracts import Pointer
from ..runtime import run_osascript

_TABS = """tell application "Safari"
  set out to ""
  repeat with w in windows
    repeat with t in tabs of w
      set out to out & (URL of t) & tab & (name of t) & linefeed
    end repeat
  end repeat
  return out
end tell"""

# A new tab in the front window, or a fresh document if Safari has no window open.
_OPEN = """on run argv
  set u to item 1 of argv
  tell application "Safari"
    if (count of windows) is 0 then
      make new document with properties {URL:u}
    else
      tell front window to make new tab with properties {URL:u}
    end if
  end tell
  return u
end run"""


def _parse(raw: str) -> list[Pointer]:
    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        url, _, name = line.partition("\t")
        out.append(Pointer(id=url, summary=name.strip() or url, deeplink=url))
    return out


def _normalize_url(url: str) -> str:
    """Trim and default the scheme to https:// so a bare host still loads."""
    u = url.strip()
    if not u:
        raise ValueError("safari_open needs a URL (got an empty string)")
    if "://" not in u:
        u = "https://" + u
    return u


class SafariAdapter:
    def get_tabs(self) -> list[Pointer]:
        """All open Safari tabs (id/deeplink = URL, summary = page title)."""
        return _parse(run_osascript(_TABS))

    def open_url(self, url: str) -> Pointer:
        """Open ``url`` in a new Safari tab (a new window if none is open)."""
        u = _normalize_url(url)
        run_osascript(_OPEN, u)
        return Pointer(id=u, summary=f"opened {u}", deeplink=u)
