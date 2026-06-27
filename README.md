# apple-mcp

One consolidated [MCP](https://modelcontextprotocol.io) server for native macOS apps — **Calendar &
Reminders** today (bidirectional), **Mail** next. Python + [FastMCP 2.0](https://github.com/PrefectHQ/fastmcp),
managed with [uv](https://docs.astral.sh/uv/).

Replaces the two Apple MCP servers a life-cockpit otherwise juggles (`apple-events` + a forked Apple
Mail MCP) with a single modular adapter layer you own.

**Status: v1 in progress** (Calendar + Reminders). See [DESIGN.md](DESIGN.md) for the
rationale, [CHANGELOG.md](CHANGELOG.md) for what's landed, and the issues for what's next.

## Tools

**Calendar & Reminders** — bidirectional (EventKit). Read `events` / `reminders` (and
`calendars` / `reminder_lists`); write `create_event` / `update_event` / `delete_event`
and `create_reminder` / `update_reminder` / `complete_reminder` — with all-day, priority,
start dates, and recurrence (an RFC 5545 `RRULE`).

**Read-only context** — `mail`, `notes`, `contacts` (name, org, phone, email), `photos`,
`messages_chats`, `safari_tabs`, `shortcuts`. Each returns *pointers* (id + one-line
summary + deeplink), never full bodies.

**Actions** — `run_shortcut`, `safari_open`, `create_contact`.

Set `APPLE_MCP_READ_ONLY=1` to register reads only — every write/action tool is skipped.

## Develop

```sh
uv sync
uv run pytest             # unit tests (mock at the adapter boundary)
uv run ruff check .       # lint (config in pyproject.toml)
uv run ruff format .      # format
uv run apple-mcp          # run the server (stdio)
```

ruff (lint + format, line-length 88) and pytest gate CI — full workflow in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Use as an MCP server

Launch off the project's own venv python — deterministic, and it carries the locked PyObjC wheels:

```json
{
  "mcpServers": {
    "apple-mcp": {
      "command": "/Users/you/Developer/apple-mcp/.venv/bin/python",
      "args": ["-m", "apple_mcp"]
    }
  }
}
```

macOS only. Calendar/Reminders use EventKit — grant access when macOS prompts (TCC).

## Prior art & credits

apple-mcp builds on prior work — the Apple Mail MCP it will port, the EventKit/Photos servers it
references, the project that pioneered the unified-Apple-MCP pattern, and FastMCP / PyObjC / the MCP
spec it depends on. See [CREDITS.md](CREDITS.md).
