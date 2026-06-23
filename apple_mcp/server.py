"""apple-mcp — FastMCP server. Tools are *thin dispatch* to adapters (see contracts.py)."""
from __future__ import annotations

from fastmcp import FastMCP

from .adapters.calendar import CalendarAdapter
from .adapters.reminders import RemindersAdapter
from .contracts import Pointer

mcp = FastMCP("apple-mcp")

_reminders = RemindersAdapter()
_calendar = CalendarAdapter()


def _emit(p: Pointer) -> dict[str, str]:
    return {"id": p.id, "summary": p.summary, "deeplink": p.deeplink}


@mcp.tool()
def ping() -> str:
    """Health check — confirms apple-mcp is alive."""
    return "apple-mcp ok"


@mcp.tool()
def reminders(due: str = "today") -> list[dict]:
    """List reminders as pointers. `due`: today | overdue | this-week | a list name."""
    return [_emit(p) for p in _reminders.get_pointers(due)]


@mcp.tool()
def events(when: str = "today") -> list[dict]:
    """List calendar events as pointers. `when`: today | week | YYYY-MM-DD."""
    return [_emit(p) for p in _calendar.get_pointers(when)]


def main() -> None:
    """Console entry point (`apple-mcp`) and `python -m apple_mcp`."""
    from .runtime import bootstrap

    bootstrap()
    mcp.run()  # stdio transport
