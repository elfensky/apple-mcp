# Changelog

All notable changes to apple-mcp are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/); the project is pre-1.0, so the public
surface may still shift between minor versions.

## [Unreleased]

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
