# CLAUDE.md — apple-mcp

One consolidated MCP server for native macOS apps. Python + **FastMCP 2.0**, managed with **`uv`**.
Full design and rationale: [DESIGN.md](DESIGN.md).

## Architecture (don't drift)

- **FastMCP 2.0 standalone.** Tools in `apple_mcp/server.py` are *thin dispatch* to adapters — no
  business logic in the tool layer.
- **Adapters = typed `Protocol`** (`apple_mcp/contracts.py`): **reads uniform**
  (`get_pointers -> list[Pointer]`), **writes per-adapter typed** (`create_reminder(ReminderData)`,
  `create_event(CalendarEventData)`). No ABC, no plugin registry (YAGNI). `Pointer(id, summary,
  deeplink)` is the citation contract — **pointers, not payload** (no full bodies by default).
- **All EventKit / native access goes through `apple_mcp/runtime.run_native()`** — a single
  serialized worker thread (EKEventStore thread-affinity + TCC). Never call EventKit off arbitrary
  threads, and never widen the executor past `max_workers=1`.
- **One adapter module per app** under `apple_mcp/adapters/`. Adding an app = add a module + mount its
  tools in `server.py`; it must not reach into another adapter. This is what lets a module later
  harden into a `lyfe` native data-plane adapter unchanged.

## Dev

```sh
uv sync
uv run pytest -q                # unit tests — mock at the adapter boundary (Protocol fakes)
uv run pytest -m integration    # real macOS / EventKit / TCC — run manually, NEVER in CI
uv run apple-mcp                # run the server (stdio)
```

## Life cockpit

Tracked in the life-cockpit vault under `#personal` (tracker: `elfensky/apple-mcp`). The cockpit is
the control plane (what to work on); this repo is where the work happens. Report progress by
opening/closing issues and PRs as usual — the cockpit pulls from the tracker on its next `/sync`.
Nothing to update in the vault; don't mirror cockpit state (milestones, due dates) here.
