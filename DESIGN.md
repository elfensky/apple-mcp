# mac-mcp — design

One consolidated MCP server (Python, FastMCP 2.0) exposing native macOS apps to LLM agents (Claude
Code / Desktop), replacing the two servers a life-cockpit otherwise consumes — `apple-events`
(Calendar/Reminders) and a forked Apple Mail MCP. It is the first move of the cockpit → `lyfe`
**"N consumed → 1 produced"** MCP inversion: each app is an adapter that later hardens into a `lyfe`
native data-plane adapter, so clean module boundaries are load-bearing.

## Why this exists (settled)

- The canonical unified server (`supermemoryai/apple-mcp`, 3k★) is **archived and unmaintained** and
  carries an *"every note returned in full"* context-bloat bug. We don't resurrect it; we own a lean
  replacement.
- **The apps don't share one access method:** Calendar/Reminders → EventKit (clean, no app-open);
  Mail/Notes/Photos → AppleScript; Shortcuts → CLI; **Journal → no API at all** (no AppleScript
  dictionary, JournalingSuggestions is read-only/iOS-only, entries are E2E-encrypted). So the
  architecture absorbs heterogeneous backends behind a uniform module surface — and **Journal is out**.

## Stack decisions (settled by an adversarial four-way debate)

- **FastMCP 2.0 (standalone)** — not the official SDK's vendored `mcp.server.fastmcp` (1.x, lags the
  spec), not the low-level `Server` (boilerplate). Thin tool layer → low lock-in.
- **`uv`** for dev (`uv sync` / `uv lock` / `uv run`); the MCP launches deterministically **off the
  venv python**: `command: <repo>/.venv/bin/python`, `args: ["-m","mac_mcp"]` (or `uv run --frozen
  --project <repo> mac-mcp`). Not `uvx` (ephemeral), not a system console_script (no lockfile / may
  lack PyObjC wheels). The same invocation becomes a launchd daemon later.
- **Adapter contract = typed `Protocol`; reads uniform, writes per-adapter typed.** A shared
  `PointerSource` Protocol (`get_pointers(query) -> list[Pointer]`); writes are typed methods
  (`create_event(CalendarEventData)`, `create_reminder(ReminderData)`), never a stringly-typed
  `create_item(dict)`. The MCP tool layer is the dispatch — no ABC, no plugin registry (YAGNI for n=1).
- **`Pointer(id, summary, deeplink)` IS the cockpit's citation grammar** (`[src:: system:id]` + an
  open-in-app deeplink) — pointers-not-payload by construction, which structurally avoids the archived
  flagship's context-bloat bug.
- **EventKit on one dedicated, serialized worker thread** (`runtime.py`). `EKEventStore` has thread
  affinity and TCC auth must be handled on a consistent thread; a generic multi-worker pool risks
  affinity bugs and a hung first-permission call. Create the store on a single
  `ThreadPoolExecutor(max_workers=1)` at startup; serialize every EventKit call through it.
- **Testing:** mock at the adapter boundary (typed-Protocol fakes); native calls live only in
  adapters, integration-tested behind `@pytest.mark.integration` — never in CI (no macOS/TCC there).

## Layout

```
mac_mcp/
  server.py        # FastMCP app: @mcp.tool() registrations = thin dispatch to adapters
  contracts.py     # Pointer + PointerSource Protocol (reads); typed write dataclasses
  runtime.py       # the single serialized EventKit worker thread + native-call dispatch
  adapters/
    calendar.py    # EventKit / PyObjC
    reminders.py   # EventKit / PyObjC
    mail.py        # AppleScript / osascript (read-only inbox search)
    notes.py       # AppleScript / osascript (title search)
    contacts.py    # AppleScript / osascript (search + create)
    photos.py      # AppleScript / osascript (Photos search command)
    safari.py      # AppleScript / osascript (list tabs + open url)
    messages.py    # AppleScript / osascript (chat list only)
    shortcuts.py   # `shortcuts` CLI (list + run)
tests/
  test_*.py        # unit (Protocol fakes); integration behind @pytest.mark.integration
```

## Scope by phase

### v1 — Calendar + Reminders, bidirectional *(shipped)*
- **Read** (EventKit): events / reminders at parity with `apple-events` → retires it.
- **Write** (EventKit): create/update/complete reminder; create/update/delete event — return stable
  ids. Both support recurrence (RFC 5545 `RRULE` subset).
- **Outbound projection** (a cockpit-side command): vault tasks/deadlines → Apple Reminders/Calendar,
  **idempotent** via a stable id written back into the task line (a new `[rem::]`/`[cal::]` field in
  the cockpit's `conventions.md`); completion reflects both ways.

### Read-only context + actions *(shipped)*
The pointers-not-payload surface turned out cheap to extend, so the "later / dropped" apps came in as
thin read adapters plus a few actions — each still returning only pointers:
- **Mail** (AppleScript): inbox subject search. Read-only — no body fetch, no send.
- **Notes** (AppleScript): title search.
- **Contacts** (AppleScript): name search → name/org/first phone+email; `create_contact` action.
- **Photos** (AppleScript `search`): media search — no PhotoKit bundle needed.
- **Safari** (AppleScript): list open tabs; `safari_open` action (http/https only).
- **Messages** (AppleScript): conversation list only — content needs the private `chat.db`, sending
  is regressed since macOS 11, so both are out.
- **Shortcuts** (`shortcuts` CLI): list shortcuts; `run_shortcut` action — a gateway to any user
  automation, no Automation prompt.

### Out — no viable path
- **Apple Journal:** no write API and no AppleScript dictionary; entries are E2E-encrypted.

## Out of scope
- A two-way conflict-resolution engine — v1 is outbound projection + id-mediated reconcile, not a
  general sync engine. Conflicts are avoided by stable ids, not resolved by merge logic.
- The `lyfe` resident daemon + unified DB — later; adapters feed it eventually, none built now.

## Tracking
Work breakdown lives as GitHub issues. The life-cockpit tracks this repo under `#personal`
(tracker `elfensky/mac-mcp`) and pulls issues onto its board via `/sync`.
