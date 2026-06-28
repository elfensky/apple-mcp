# Round out the Notes surface (#40)

**Status:** approved design, pre-implementation.
**Issue:** [elfensky/apple-mcp#40](https://github.com/elfensky/apple-mcp/issues/40)
**Verified by:** 4-way blind debate (Codex, Gemini, Sonnet, Opus) — 5 amendments folded in.

## Problem

The Notes surface is search-only. `notes(title)` returns `id + title` pointers and
nothing else. That can't drive a real Notes workflow — the motivating case is
bulk-importing all Apple Notes into a vault, de-duplicating, and cleaning up. Three gaps:
list **all** notes, read note **bodies**, **delete** a note.

`osascript` already backs the adapter (`adapters/notes.py` is `tell application "Notes"`),
so this exposes mechanisms that already work, through the MCP.

## Approach

Three new tools on the existing osascript + `Pointer` pattern. User input flows through
`run_osascript(script, *argv)` → `on run argv` (never string-interpolated; injection-safe),
exactly like the current `_SEARCH`. No new dependencies, no native imports in the adapter.

## Decisions (settled)

1. **Folder placement** — add `folder: str | None = None` to the frozen `Pointer`
   dataclass (4th field, defaulted ⇒ existing positional `Pointer(id, summary, deeplink)`
   calls untouched). Value is `"Account / Folder"`. Chosen over a plain dict (would break
   the *reads-return-Pointer* invariant the cockpit citation grammar depends on) and over
   a `metadata: dict` (the stringly-typed anti-pattern `contracts.py` argues against). A
   dormant optional typed field is the smallest change the architecture absorbs.
2. **`notes_all` cap** — none, no pagination. Bulk property access makes producing the
   full list cheap; pagination would only slice an already-fetched list. The 30s
   `_OSASCRIPT_TIMEOUT` is the de-facto ceiling and failure is all-or-nothing — documented
   in the docstring, not left implicit. Upgrade path (YAGNI): add `offset`/`limit` later
   if response size or timeout bites.
3. **`note_bodies` batch cap** — 50 ids/call (raise `ValueError` if exceeded).

## Amendments from the debate (baked into this design)

- **#1 — atomic id/name alignment (blocking).** Do **not** fetch `id of every note` and
  `name of every note` as two separate Apple events (they can mispair if Notes mutates
  between calls). Use a single multi-property read `{id, name} of (notes of f)` → both
  parallel lists from one snapshot, then loop by index over the in-memory lists.
- **#2 — account-qualified folders (blocking).** Folder names collide across accounts
  (`"Notes"` in both iCloud and On My Mac). Iterate `accounts` → `folders of acc` and emit
  `folder = "<account> / <folder>"` so dedup workflows can tell them apart. (Note ids are
  `x-coredata://` URLs that embed the store id, so they are globally unique — delete-by-id
  is unambiguous; the collision is a *display/dedup* concern, not an id one.)
- **#3 — O(n) string build + documented ceiling.** Build lines with `set end of theLines`
  and join via `AppleScript's text item delimiters` (avoids O(n²) `&` concatenation that
  compounds the timeout on large libraries). Docstring states the 30s all-or-nothing
  ceiling.
- **#4 — safer delete.** Optional `expect_title`: when supplied, the script verifies the
  note's current title matches before deleting (guards stale/wrong ids). Delete is
  recoverable (Recently Deleted, ~30 days); docstring says "content-verify before deleting".
- **#5 — delimiter round-trip test.** `note_bodies` uses ASCII control chars as
  delimiters; add one integration test that round-trips a body containing newlines/tabs
  through real osascript to guard against a future macOS change.

## Components

### 1. `apple_mcp/contracts.py` — `Pointer` gains `folder`

```python
@dataclass(frozen=True, slots=True)
class Pointer:
    id: str
    summary: str
    deeplink: str
    folder: str | None = None  # notes_all only: "Account / Folder"; None elsewhere
```

Docstring updated to note `folder` is currently notes-specific and dormant (`None`) for
all other adapters.

### 2. `apple_mcp/server.py` — `_emit` includes `folder` only when set

```python
def _emit(p: Pointer) -> dict[str, str]:
    d = {"id": p.id, "summary": p.summary, "deeplink": p.deeplink}
    if p.folder is not None:
        d["folder"] = p.folder
    return d
```

Other adapters' tool output stays byte-identical (folder is `None` ⇒ key omitted).

### 3. `apple_mcp/adapters/notes.py` — three additions

Constants: `MAX_BODIES = 50`.

**`get_all() -> list[Pointer]`** — every note, no cap, account-qualified, atomic alignment.

```applescript
on run argv
  set theLines to {}
  tell application "Notes"
    repeat with acc in accounts
      set accName to name of acc
      repeat with f in folders of acc
        if name of f is not "Recently Deleted" then
          set {theIds, theNames} to ({id, name} of (notes of f))
          repeat with i from 1 to (count of theIds)
            set end of theLines to ((item i of theIds) & tab & accName & " / " & (name of f) & tab & (item i of theNames))
          end repeat
        end if
      end repeat
    end repeat
  end tell
  set AppleScript's text item delimiters to linefeed
  return theLines as text
end run
```

New `_parse_all(raw)` splits each line on tab → `id`, `folder` (= "account / folder"),
`title` → `Pointer(id=id, summary=title or "(untitled note)", deeplink="", folder=folder)`.
Blank lines skipped (matches `_parse`). Docstring documents the 30s all-or-nothing ceiling
and the localized-"Recently Deleted" caveat (see Known limitations).

**`get_bodies(ids: list[str]) -> list[dict]`** — opt-in batched body hydration.

```applescript
on run argv
  set out to ""
  tell application "Notes"
    repeat with theId in argv
      try
        set out to out & theId & (character id 31) & (plaintext of note id theId) & (character id 30)
      end try
    end repeat
  end tell
  return out
end run
```

- Adapter validation: empty `ids` → `ValueError`; `len(ids) > MAX_BODIES` → `ValueError`
  with guidance to chunk (honest boundary error, not silent truncation).
- Control-char delimiters: `character id 31` (US, `\x1f`) between id and body,
  `character id 30` (RS, `\x1e`) between records. Chosen over the issue's `@@@END@@@`
  because note bodies contain newlines/tabs/arbitrary text — a literal-text sentinel can
  be present in a body and corrupt parsing; control chars effectively cannot. Parser
  splits raw on `\x1e`, then `partition("\x1f")` → `{"id", "body"}`. Empty records skipped.
- Unknown/bad ids are skipped (`try` per id); the caller diffs returned vs requested ids.

**`delete(ident: str, expect_title: str | None = None) -> None`** — recoverable delete.

```applescript
on run argv
  tell application "Notes"
    set n to note id (item 1 of argv)
    if (count of argv) > 1 then
      if (name of n) is not (item 2 of argv) then error "note title does not match expect_title"
    end if
    delete n
  end tell
end run
```

- Adapter validation: empty `ident` → `ValueError`.
- `expect_title` (when given) is passed as `argv[2]`; mismatch raises in AppleScript →
  surfaced as `RuntimeError` by `run_osascript`. Delete moves the note to Recently Deleted
  (recoverable ~30 days).

### 4. `apple_mcp/server.py` — wiring

```python
@mcp.tool()
def notes_all() -> list[dict]:
    """List every note as pointers (id + "Account / Folder" + title), excluding Recently
    Deleted. No cap; very large libraries can hit the osascript timeout (all-or-nothing)."""
    return [_emit(p) for p in _notes.get_all()]

@mcp.tool()
def note_bodies(ids: list[str]) -> list[dict]:
    """Hydrate plaintext bodies for up to 50 note ids (opt-in; search stays pointer-only).
    Returns [{"id", "body"}]; unknown ids are silently skipped."""
    return _notes.get_bodies(ids)

@_write_tool
def delete_note(id: str, expect_title: str | None = None) -> dict:
    """Delete a note by id → Recently Deleted (recoverable ~30 days). Destructive.
    Pass expect_title to verify the target before deleting (content-verify first)."""
    _notes.delete(id, expect_title)
    return {"deleted": id}
```

`notes_all` / `note_bodies` are reads (`@mcp.tool()`); `note_bodies` deliberately returns
payload — the explicit, batched escape hatch from "pointers, not payload". `delete_note`
is `@_write_tool` ⇒ unregistered under `APPLE_MCP_READ_ONLY` (like `delete_event`).

### 5. Tests

`tests/test_notes.py` (pure parsing/validation, no osascript):
- `_parse_all`: id + "account / folder" + title; untitled → "(untitled note)"; blank-skip;
  a title is single-line so tab/linefeed delimiting is safe.
- bodies parser: split on `\x1e`/`\x1f`; multi-line bodies preserved intact; bad/empty
  records skipped.
- `get_bodies([])` raises; `get_bodies([…51 ids…])` raises.
- `delete("")` raises.

`tests/test_server.py`: `_emit` includes `folder` when set, omits when `None`.

`tests/test_integration.py` (real Notes.app, `-m integration`, manual, never CI):
- create → `get_all` finds it with the right account-qualified folder;
- body with newlines + tabs round-trips through `get_bodies` byte-for-byte (#5 guard);
- `delete` with a matching `expect_title` succeeds; mismatched `expect_title` raises and
  leaves the note in place.

## Invariants preserved

- `notes()` stays search-only and pointer-only. Bodies are explicit / batched / capped.
- Reads return `Pointer`; writes are typed per-adapter; native access through
  `run_osascript`; destructive tool gated by `@_write_tool`.
- All three tools need the same Notes Automation (TCC) permission `notes()` already needs.

## Known limitations (documented, not fixed)

- **Localized "Recently Deleted".** The exclusion matches the English folder name; on a
  localized macOS the trash folder is named differently and would be included. AppleScript
  exposes no stable locale-independent handle for it. Documented; revisit if a non-English
  user hits it.
- **No-cap timeout.** A very large library can exceed the 30s osascript timeout; the call
  fails whole (no partial results). Upgrade path is `offset`/`limit` pagination.
- **Body delimiter.** Control chars `\x1e`/`\x1f` are assumed absent from note plaintext —
  effectively always true, but a deliberately pasted control char would split a record.
  Acceptable; the integration test guards the transport.

## Non-issues (cleared by the debate)

- `run_osascript` returns `""` on empty stdout (raises only on non-zero exit), so an empty
  vault → `_parse_all("")` → `[]`. Do **not** add a "non-empty output" guard.
- Control-char bytes survive `osascript` → Python (`text=True`); transport is fine.
