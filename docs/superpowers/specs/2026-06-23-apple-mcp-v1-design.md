# apple-mcp v1 — design spec

- **Date:** 2026-06-23
- **Status:** approved (brainstorming); next step is an implementation plan
- **Issues:** #1–#5 (GitHub `elfensky/apple-mcp`)
- **Supersedes nothing.** Extends [DESIGN.md](../../../DESIGN.md) with the concrete v1 build plan; the
  stack and architecture in DESIGN.md / CLAUDE.md are settled and not re-litigated here.

## 1. Context

apple-mcp is one consolidated FastMCP 2.0 server exposing native macOS apps to LLM agents. v1 covers
**Calendar + Reminders, bidirectional**, via EventKit, and retires the cockpit's `apple-events`
dependency. Why this exists, the heterogeneous-backend rationale, and the settled stack decisions live
in [DESIGN.md](../../../DESIGN.md). This document is the v1 *plan*: what each issue delivers, where the
boundaries are, how it's tested and maintained, and what we explicitly do not build.

## 2. Decisions locked in this session

1. **Compatibility = rolling latest-stable macOS only.** Target the latest stable release (macOS 26
   Tahoe today); the floor moves forward with each macOS release. **No back-compat shims** — use the
   macOS 14+ `requestFullAccessToEvents` / `requestFullAccessToReminders` APIs only, never the
   deprecated `requestAccessToEntityType`.
2. **#4 (projection) and #5 (retire apple-events) are cross-repo.** Their *deliverable in this repo* is
   a contract / checklist; their *execution* happens in the life-cockpit repo, which this repo's
   CLAUDE.md says not to touch. #1–#3 are pure apple-mcp code.
3. **"Parity" means the briefing, not feature-parity with apple-events.** `apple-events` exposes a huge
   surface (tags, recurrence, subtasks, alarms, geofences, structured locations). v1 covers only what
   the cockpit's `/today` briefing consumes; everything else is an explicit non-goal (§9).

## 3. Scope & the cross-repo boundary

| Issue | Deliverable in this repo | Executed where |
|---|---|---|
| #1 runtime | EKEventStore + TCC on the single serialized worker | here (code) |
| #2 reads | `get_pointers` for reminders + calendar | here (code) |
| #3 writes | create/update/complete reminder; create/update/delete event | here (code) |
| #4 projection | **contract spec** — `[rem::]`/`[cal::]` grammar + idempotent reconcile algorithm | cockpit (later) |
| #5 retire apple-events | **parity checklist** confirming the briefing is covered | cockpit (MCP config + `meta/SETUP.md`) |

**v1-in-this-repo is done when** #1–#3 are implemented and on-device-verified, the #4 contract doc and
#5 checklist are written. The two cockpit edits happen separately, in the cockpit.

## 4. Compatibility & maintenance policy

- **macOS:** latest stable only, rolling (macOS 26 Tahoe now). No version-gated branches.
- **Python ≥ 3.11**, **pyobjc-framework-EventKit ≥ 10**, **fastmcp ≥ 2.0**. `uv.lock` is the
  source of truth for reproducible runs; floors stay as `>=`.
- **Launch:** off the venv python (`<repo>/.venv/bin/python -m apple_mcp`) or
  `uv run --frozen --project <repo> apple-mcp` — per DESIGN.md, never `uvx`.
- **CONTRIBUTING.md** documents: dev setup (`uv sync`, `uv run pytest -q`), the `run_native`
  invariant, the one-adapter-per-app rule, and how to run integration tests manually.
- **Releases:** git tags + GitHub Releases. **No maintained CHANGELOG file** — git history suffices
  for a solo repo.

## 5. Per-issue design

### #1 — single-thread EventKit runtime (`runtime.py`)

- **`runtime` owns the `EKEventStore`** (lazily created *inside* the worker thread), not an adapter.
  Rationale: a single source of truth, both entity types from one store, and it honors CLAUDE.md's
  "no adapter reaches into another adapter" invariant (the stubs' "calendar shares reminders' store"
  would violate it).
- `store()` accessor asserts it is called on the worker thread; adapters depend on `runtime`, never on
  each other.
- `request_access()` calls both `requestFullAccess*` APIs on the worker, blocking on a
  `threading.Event` for the completion handler (the callback fires on a GCD queue, not our worker —
  the standard block-and-wait pattern).
- A **pure** `_decide(status) -> None | raise AccessDenied` helper maps the EventKit authorization
  status enum to a decision (unit-testable without EventKit). `AccessDenied` carries a human message:
  *"grant access in System Settings → Privacy & Security → Calendars / Reminders."*
- **Eager bootstrap at startup** via `run_native`: create the store, request both accesses. Denial is
  **non-fatal** (logged; `ping` still works; access-needing tools raise `AccessDenied`) — graceful
  degradation per issue #1.

### #2 — read adapters (reminders + calendar)

- Each adapter implements the settled `get_pointers(query: str) -> list[Pointer]`.
- `query` is a small **documented selector** (no free-text search engine in v1):
  - calendar: `today` | `week` | `YYYY-MM-DD`
  - reminders: `today` | `overdue` | `this-week` | a list name
- **Pointer mapping is a pure function** `item -> Pointer` over a duck-typed item, so unit tests need
  no EventKit.
  - `id` = `calendarItemIdentifier` (local stable id; the `externalIdentifier` / recurring-occurrence
    gotcha is documented in code).
  - `summary` = one line (`"Title 09:00–10:00"`, `"Title — due 2026-06-23"`) — never notes/body
    (pointers-not-payload).
  - `deeplink` = best-effort scheme; **on-device-verify** (§6).

### #3 — write tools (reminders + calendar)

- Adapter methods, all via `run_native`, each returning a `Pointer` (delete returns a confirmation):
  - reminders: `create_reminder(ReminderData)`, `update_reminder(id, ReminderData)`,
    `complete_reminder(id)`
  - calendar: `create_event(CalendarEventData)`, `update_event(id, CalendarEventData)`,
    `delete_event(id)`
- **Update = full-replace from the typed payload.** This matches projection's "re-derive the item
  from the vault task each run" model, which makes it idempotent and avoids patch-merge complexity.
- **List/calendar resolved by name**; a missing name raises a clear error (no silent auto-create).
  `None` falls back to `defaultCalendarForNewReminders` / `defaultCalendarForNewEvents`.
- EventKit saves (`saveReminder:commit:error:`, `saveEvent:span:commit:error:`,
  `removeEvent:span:commit:error:`) map a failed `BOOL`/`NSError` to a clear exception.
- **Server tools** are thin `@mcp.tool()` wrappers: build the typed payload → `run_native` → adapter
  → return the `Pointer`.

### #4 — projection contract (doc only, here)

`docs/projection-contract.md` defines:

- The `[rem:: <id>]` / `[cal:: <id>]` field written back into a vault task line, placed **before the
  date emoji** (the Obsidian Tasks-plugin ordering gotcha).
- The id-mediated **idempotent** algorithm: no `[rem::]` → create + write back id; present → update;
  vault task done → complete the reminder; reminder completed in Apple → reflect back to the vault.
- No conflict-merge engine (DESIGN.md out-of-scope) — conflicts are *avoided* by stable ids.
- The MCP tools the cockpit command will call (the #3 writes + a read to check completion).
- Explicit note: **implemented in the cockpit**, not here.

### #5 — retire apple-events (checklist, here)

`docs/parity-checklist.md` maps each `/today` briefing read to its apple-mcp equivalent. When the
checklist passes (briefing renders identically off apple-mcp), the cockpit drops `apple-events` from
its MCP config and updates `meta/SETUP.md`.

## 6. Known risks to verify on-device

1. **Deeplinks to a specific reminder/event are not well-documented publicly.** v1 verifies the actual
   scheme on this Mac and either uses the working format or falls back to an app/date-open link
   (a calibration knob the physical OS dictates, not the model).
2. **TCC completion-handler threading.** The `requestFullAccess*` callback lands off our worker; the
   block-and-wait must be correct or first-run auth hangs. Exercised by the #1 integration smoke test
   (`uv run apple-mcp`).

## 7. Testing strategy + CI

- **Unit (CI-safe, no macOS):** the pure mappers — `_decide(status)`, `item → Pointer`,
  `payload → typed`, and tool → adapter dispatch via `Protocol` fakes. Run by `uv run pytest -q`.
- **Integration (`@pytest.mark.integration`, this Mac, manual, never CI):** real auth, read, and
  create/complete/update/delete against a dedicated `apple-mcp-test` list/calendar, **with cleanup**.
- **Default-deselect integration:** add `addopts = "-m 'not integration'"` to `pyproject.toml` so
  `pytest -q` is safe everywhere and `pytest -m integration` opts in.
- **CI:** one GitHub Actions job on `macos-latest` running `uv sync && uv run pytest -q` (unit only —
  PyObjC is macOS-only, so no Linux runner; TCC-gated tests stay out of CI).

## 8. Milestone, sequencing, artifacts

- GitHub **milestone "v1: Calendar + Reminders"** holds #1–#5; each issue refined with the acceptance
  criteria in §10.
- **Build order:** #1 → #2 → #3 (TDD each: unit first, then on-device smoke), then write the #4
  contract doc and #5 checklist.
- **New artifacts:**
  - `docs/superpowers/specs/2026-06-23-apple-mcp-v1-design.md` (this spec)
  - `CONTRIBUTING.md`
  - `.github/workflows/ci.yml`
  - `docs/projection-contract.md` (#4)
  - `docs/parity-checklist.md` (#5)
  - `pyproject.toml` `addopts` line
  - refined GitHub issues + the milestone

## 9. Non-goals (explicit v1 exclusions)

Deliberately **not** in v1, to keep "parity" honest and the surface lean:

- Reminder/event **tags, recurrence, subtasks, alarms, geofences/location triggers, structured
  locations, priority, URLs** — apple-events features we omit until a concrete need appears.
- A **free-text search** engine over items (only the §5 selectors).
- A **two-way conflict-resolution / merge engine** (DESIGN.md out-of-scope).
- **Mail** (v1.5), **Notes** (dropped), **Photos** (Immich), **Journal** (no write API), **Messages /
  Contacts** (YAGNI).

## 10. Refined acceptance criteria (per issue)

**#1 runtime**
- EKEventStore created on the single worker; `store()` rejects off-worker calls.
- `request_access()` returns full access on this Mac; denial raises `AccessDenied` with the grant
  message; server still boots (graceful degradation).
- `_decide(status)` unit-tested for every status value.
- `uv run apple-mcp` boots and triggers the TCC prompt on first run (integration smoke).

**#2 reads**
- `RemindersAdapter.get_pointers` returns Pointers for `today` / `overdue` / `this-week` / a list name.
- `CalendarAdapter.get_pointers` returns Pointers for `today` / `week` / a date.
- Every Pointer has a stable `id`, a one-line `summary` (no body), and a `deeplink`.
- `item → Pointer` mapping unit-tested with fakes; reads verified on-device (integration).

**#3 writes**
- create/update/complete reminder and create/update/delete event each succeed on-device and return a
  Pointer (delete → confirmation).
- Missing list/calendar name raises a clear error; `None` uses the default.
- tool → adapter dispatch unit-tested via Protocol fakes; round-trips verified on-device against the
  `apple-mcp-test` list/calendar with cleanup.

**#4 projection contract**
- `docs/projection-contract.md` defines the grammar, placement rule, idempotent algorithm, and the
  tool surface; states it is built in the cockpit.

**#5 retire apple-events**
- `docs/parity-checklist.md` enumerates every briefing read and its apple-mcp equivalent; passing it
  is the gate for the cockpit-side removal.
