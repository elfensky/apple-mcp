# apple-mcp

One consolidated [MCP](https://modelcontextprotocol.io) server for native macOS apps —
**Calendar & Reminders** read/write, plus read-only context and a few actions across Mail,
Notes, Contacts, Photos, Safari, Messages, and Shortcuts. Python +
[FastMCP 2.0](https://github.com/PrefectHQ/fastmcp), managed with
[uv](https://docs.astral.sh/uv/).

Replaces the two Apple MCP servers a life-cockpit otherwise juggles (`apple-events` + a forked
Apple Mail MCP) with a single modular adapter layer you own. Every read returns **pointers**
(id + one-line summary + open-in-app deeplink), never full bodies — so it structurally avoids
the context-bloat bug of the archived flagship server.

See [DESIGN.md](DESIGN.md) for the rationale and [CHANGELOG.md](CHANGELOG.md) for what's landed.

## Tools

Reads return pointers; results are capped per adapter. Writes/actions are skipped entirely when
`APPLE_MCP_READ_ONLY` is set (see below).

### Calendar & Reminders — read/write (EventKit)

| Tool | Args | Notes |
|------|------|-------|
| `events` | `when` = `today` \| `week` \| `YYYY-MM-DD` | list events as pointers |
| `reminders` | `due` = `today` \| `overdue` \| `this-week` \| a list name | list reminders as pointers |
| `calendars` | — | calendars (id + name) to target writes |
| `reminder_lists` | — | reminder lists (id + name) to target writes |
| `create_event` / `update_event` | title, start, end (ISO), calendar, location, notes, `all_day`, `recurrence` | `update` is a full replace by id |
| `delete_event` | id | |
| `create_reminder` / `update_reminder` | title, due, list_name, notes, `priority` (0–9), start, `recurrence` | `update` is a full replace by id |
| `complete_reminder` | id | marks complete |

**Recurrence** is an RFC 5545 `RRULE` string — the `FREQ` / `INTERVAL` / `COUNT` / `UNTIL`
subset (e.g. `FREQ=WEEKLY;INTERVAL=2;COUNT=10`). A recurring reminder requires a due date;
unsupported parts (`BYDAY`, …) are rejected rather than silently ignored.

### Read-only context (AppleScript / CLI)

| Tool | Args | Returns |
|------|------|---------|
| `mail` | subject substring | inbox matches (subject + sender) |
| `notes` | title substring | matching notes (id + title) |
| `contacts` | name substring | cards (name, org, first phone + email) |
| `photos` | search string | media (filename); matches the Photos search field |
| `safari_tabs` | — | every open tab (url + title) |
| `messages_chats` | — | conversation list (id + name; **no message content**) |
| `shortcuts` | name substring (empty = all) | the user's Shortcuts (name) |
| `ping` | — | health check |

### Actions (writes)

| Tool | Args | Notes |
|------|------|-------|
| `create_contact` | given_name, family_name, organization | |
| `run_shortcut` | name, optional `input_text` | runs a Shortcut; returns a bounded output snippet |
| `safari_open` | url | opens in a new tab; bare host → `https://`; only `http`/`https` allowed |

### Read-only mode

Set `APPLE_MCP_READ_ONLY=1` (or `true` / `yes`) to register reads only — every write and action
tool above is skipped, a safe-deploy guard.

## Develop

```sh
uv sync
uv run pytest                   # unit tests (mock at the adapter boundary)
uv run pytest -m integration    # real macOS / EventKit / TCC — run manually, never in CI
uv run ruff check .             # lint (config in pyproject.toml)
uv run ruff format .            # format
uv run apple-mcp                # run the server (stdio)
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

macOS only. Calendar/Reminders use EventKit; the other adapters script their apps via Automation.
Grant access when macOS prompts (TCC) — the first call to each app triggers its permission dialog.

## Prior art & credits

apple-mcp builds on prior work — the Apple Mail MCP it draws from, the EventKit/Photos servers it
references, the project that pioneered the unified-Apple-MCP pattern, and FastMCP / PyObjC / the MCP
spec it depends on. See [CREDITS.md](CREDITS.md).
</content>
