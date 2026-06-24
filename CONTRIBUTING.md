# Contributing to apple-mcp

## Setup
```sh
uv sync
```

## Tests
```sh
uv run pytest                 # unit tests — no macOS access needed; this is what CI runs
uv run pytest -m integration  # real EventKit / TCC — this Mac only, grant access when prompted; NEVER in CI
```

## Run the server
```sh
uv run apple-mcp              # stdio transport
```

## Lint & format
```sh
uv run ruff check .          # lint
uv run ruff check . --fix    # lint with autofix
uv run ruff format .         # format
uv run ruff format --check . # check formatting, no writes — what CI runs
```
ruff config lives in `pyproject.toml` (line-length 88; rules `E, F, I, UP, B, SIM`) — the same setup
as the sibling repos. Before committing, run the full chain and report real output rather than
suppressing failures:
```sh
uv run pytest && uv run ruff check . && uv run ruff format --check .
```
Commits follow conventional-commit prefixes (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`).

## Non-negotiable invariants
- **All EventKit / native access goes through `runtime.run_native`** (one serialized worker, `max_workers=1`). Never widen the executor; never touch `EKEventStore` from another thread.
- **The `EKEventStore` is owned by `runtime`, not by an adapter.** One adapter must never import or reach into another.
- **Reads return `Pointer`s** (`get_pointers(query) -> list[Pointer]`); **writes take typed dataclasses** (`ReminderData`, `CalendarEventData`). Tools in `server.py` are thin dispatch only.
- **Pointers, not payload** — `id` + one-line `summary` + `deeplink`, never full bodies.
- One adapter module per app under `apple_mcp/adapters/`. Adding an app = add a module + mount its tools in `server.py`.

## Compatibility
Latest stable macOS only (rolling). We use the macOS 14+ full-access APIs; we do not carry back-compat shims.
