"""Safari adapter — Safari.app via osascript (Automation TCC). Read-only: open tabs.

Lists every open tab across windows. ``Pointer.id`` and ``deeplink`` are the tab URL;
``summary`` is the page title. No user input, so no argv. Pointers, not page content.
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


def _parse(raw: str) -> list[Pointer]:
    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        url, _, name = line.partition("\t")
        out.append(Pointer(id=url, summary=name.strip() or url, deeplink=url))
    return out


class SafariAdapter:
    def get_tabs(self) -> list[Pointer]:
        """All open Safari tabs (id/deeplink = URL, summary = page title)."""
        return _parse(run_osascript(_TABS))
