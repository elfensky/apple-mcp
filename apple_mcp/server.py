"""apple-mcp — FastMCP server. Tools are *thin dispatch* to adapters (see contracts.py)."""

from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("apple-mcp")


@mcp.tool()
def ping() -> str:
    """Health check — confirms apple-mcp is alive."""
    return "apple-mcp ok"


# v1 (see GitHub issues): mount the EventKit-backed tools here, each a thin dispatch to
# adapters.{reminders,calendar} via runtime.run_native():
#   - reads  -> list[Pointer]    (reminders_today, events_today, ...)
#   - writes -> typed payloads   (create_reminder(ReminderData), create_event(CalendarEventData))


def main() -> None:
    """Console entry point (`apple-mcp`) and `python -m apple_mcp`."""
    mcp.run()  # stdio transport
