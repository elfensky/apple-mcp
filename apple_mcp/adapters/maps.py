"""Maps adapter — open Maps via URL scheme (#17).

Maps has NO AppleScript dictionary (confirmed via ``sdef``), so there is no structured
read — only opening the app to a query. This is a thin action over ``open maps://?q=…``
(LaunchServices), the same approach the reference apple-mcp servers use. Open-only.
"""

from __future__ import annotations

import subprocess
import urllib.parse

_TIMEOUT = 10.0  # seconds


def _maps_url(query: str) -> str:
    q = query.strip()
    if not q:
        raise ValueError("maps needs a query (got an empty string)")
    return "maps://?q=" + urllib.parse.quote(q)


class MapsAdapter:
    def open_search(self, query: str) -> str:
        """Open Maps to a search (place or address). Returns the URL opened."""
        url = _maps_url(query)
        proc = subprocess.run(
            ["open", url], capture_output=True, text=True, timeout=_TIMEOUT
        )
        if proc.returncode != 0:
            raise RuntimeError(f"open maps failed: {proc.stderr.strip()}")
        return url
