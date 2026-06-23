# Contributing to apple-mcp

## Setup
```sh
uv sync
```

## Tests
```sh
uv run pytest -q              # unit tests — no macOS access needed; this is what CI runs
uv run pytest -m integration  # real EventKit / TCC — this Mac only, grant access when prompted; NEVER in CI
```

## Run the server
```sh
uv run apple-mcp              # stdio transport
```

## Non-negotiable invariants
- **All EventKit / native access goes through `runtime.run_native`** (one serialized worker, `max_workers=1`). Never widen the executor; never touch `EKEventStore` from another thread.
- **The `EKEventStore` is owned by `runtime`, not by an adapter.** One adapter must never import or reach into another.
- **Reads return `Pointer`s** (`get_pointers(query) -> list[Pointer]`); **writes take typed dataclasses** (`ReminderData`, `CalendarEventData`). Tools in `server.py` are thin dispatch only.
- **Pointers, not payload** — `id` + one-line `summary` + `deeplink`, never full bodies.
- One adapter module per app under `apple_mcp/adapters/`. Adding an app = add a module + mount its tools in `server.py`.

## Compatibility
Latest stable macOS only (rolling). We use the macOS 14+ full-access APIs; we do not carry back-compat shims.
