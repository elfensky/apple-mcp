# Changelog

All notable changes to apple-mcp are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/); the project is pre-1.0, so the public
surface may still shift between minor versions.

## [Unreleased]

## [0.1.1] - 2026-06-28

Docs-only release — the shipped tool surface was unchanged; the narrative docs
had drifted behind it.

### Changed

- **README** rewritten around the actual surface: the stale "Calendar + Reminders,
  Mail next / v1 in progress" framing is replaced by tables covering the read/write
  Calendar & Reminders tools, the read-only context adapters (Mail, Notes, Contacts,
  Photos, Safari, Messages, Shortcuts), and the actions — with real args, query
  selectors, the `RRULE` subset, and the `APPLE_MCP_READ_ONLY` guard.
- **DESIGN.md** reconciled with shipped reality: the read adapters it had listed as
  "dropped" / "YAGNI" / "maybe-never" (Notes, Messages, Contacts, Photos) are
  documented as shipped; the layout block lists all nine adapters; Photos is noted as
  AppleScript (not `osxphotos`).

### Removed

- **`docs/superpowers/`** — the executed v1 plan and its design spec. Both were spent
  build-time scaffolding; their durable decisions live in DESIGN.md / CLAUDE.md, and
  the spec had gone stale (it predated the CHANGELOG and the recurrence/Notes/Messages/
  Contacts work). The living cross-repo contracts (`docs/projection-contract.md`,
  `docs/parity-checklist.md`) are kept.

## [0.1.0] - 2026-06-27

First tagged release.

### Added

- **Recurrence** for Calendar events and Reminders — pass an RFC 5545 `RRULE` string
  (the `FREQ` / `INTERVAL` / `COUNT` / `UNTIL` subset) to `create_event` / `update_event`
  and `create_reminder` / `update_reminder`. A recurring reminder requires a due date
  (enforced at the boundary as a clear error); `INTERVAL`/`COUNT` must be positive, a
  date-only `UNTIL` includes the whole final day, and unsupported RRULE parts (e.g.
  `BYDAY`) are rejected rather than silently ignored.
- **`run_shortcut`** — run a Shortcut by name with optional text input, via the
  `shortcuts` CLI; returns a bounded snippet of any output.
- **`safari_open`** — open a URL in a new Safari tab; a bare host defaults to `https://`,
  and only `http`/`https` URLs are opened (non-web schemes are refused at the boundary).
- **Calendar `all_day`** flag on event create/update.
- **Reminder `priority`** (0–9) and **`start`** date on reminder create/update.
- **Contacts** read now surfaces the first phone + email in the pointer summary — a
  reachable handle, not just name + organization.

### Removed

- **Music adapter** — track search and the proposed playback control are dropped as the
  weakest tool, following the earlier removal of the Files and Maps adapters.

### Notes

- The new action tools (`run_shortcut`, `safari_open`) are guarded by
  `APPLE_MCP_READ_ONLY` like every other write, so a read-only deployment still skips them.
