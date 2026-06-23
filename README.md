# apple-mcp

One consolidated [MCP](https://modelcontextprotocol.io) server for native macOS apps — **Calendar &
Reminders** today (bidirectional), **Mail** next. Python + [FastMCP 2.0](https://github.com/jlowin/fastmcp),
managed with [uv](https://docs.astral.sh/uv/).

Replaces the two Apple MCP servers a life-cockpit otherwise juggles (`apple-events` + a forked Apple
Mail MCP) with a single modular adapter layer you own.

**Status: v1 in progress** (Calendar + Reminders). See [DESIGN.md](DESIGN.md) and the issues.

## Develop

```sh
uv sync
uv run pytest -q          # unit tests (mock at the adapter boundary)
uv run apple-mcp          # run the server (stdio)
```

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
