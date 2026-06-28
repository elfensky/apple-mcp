# Notes Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three Notes tools — `notes_all` (list every note), `note_bodies` (opt-in body hydration), `delete_note` (recoverable delete) — to round out the search-only Notes surface (issue #40).

**Architecture:** Thin MCP tools in `server.py` dispatch to `NotesAdapter`, which drives Notes.app via `run_osascript(script, *argv)` (user input via `on run argv`, never interpolated). Reads return `Pointer`; `note_bodies` is the explicit payload escape hatch. `Pointer` gains an optional `folder` field carrying `"Account / Folder"`.

**Tech Stack:** Python 3.11+, FastMCP 2.0, `uv`, `pytest`, `ruff`. AppleScript via `osascript`.

**Spec:** `docs/superpowers/specs/2026-06-28-notes-surface-design.md`

## Global Constraints

- Ruff config: line-length 88, rules `E, F, I, UP, B, SIM`. Run `uv run ruff check .` and `uv run ruff format --check .` clean before every commit.
- Unit tests mock at the adapter boundary — **never** call `osascript`. Real Notes.app coverage goes in `tests/test_integration.py`, marked `@pytest.mark.integration`, run manually, never in CI.
- All native access goes through `apple_mcp/runtime.run_osascript`; the adapter imports no native modules.
- Destructive tools use the `@_write_tool` decorator so they unregister under `APPLE_MCP_READ_ONLY`.
- `from __future__ import annotations` at the top of every module (existing convention).
- Verification command (run all three, report real output): `uv run pytest && uv run ruff check . && uv run ruff format --check .`

## File Structure

- `apple_mcp/contracts.py` — modify: add `folder` to `Pointer`.
- `apple_mcp/server.py` — modify: `_emit` folder handling; add `notes_all`, `note_bodies`, `delete_note` tools.
- `apple_mcp/adapters/notes.py` — modify: add `MAX_BODIES`, three AppleScript constants, `_parse_all`, `_parse_bodies`, and `get_all` / `get_bodies` / `delete` methods.
- `tests/test_contracts.py` — modify: `Pointer.folder` defaulting.
- `tests/test_server.py` — modify: `_emit` folder include/omit; three tool-dispatch tests.
- `tests/test_notes.py` — modify: `_parse_all`, `_parse_bodies`, validation tests.
- `tests/test_integration.py` — modify: real Notes round-trip tests.

---

### Task 1: `Pointer.folder` field + `_emit` handling

**Files:**
- Modify: `apple_mcp/contracts.py:26-37` (the `Pointer` dataclass)
- Modify: `apple_mcp/server.py:44-45` (`_emit`)
- Test: `tests/test_contracts.py`, `tests/test_server.py`

**Interfaces:**
- Produces: `Pointer(id: str, summary: str, deeplink: str, folder: str | None = None)`; `srv._emit(p: Pointer) -> dict[str, str]` includes key `"folder"` iff `p.folder is not None`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_contracts.py` (append):

```python
def test_pointer_folder_defaults_none():
    p = Pointer(id="x", summary="s", deeplink="d")
    assert p.folder is None


def test_pointer_folder_set():
    p = Pointer(id="x", summary="s", deeplink="d", folder="iCloud / Notes")
    assert p.folder == "iCloud / Notes"
```

In `tests/test_server.py` (append):

```python
def test_emit_omits_folder_when_none():
    out = srv._emit(Pointer(id="P-1", summary="s", deeplink="d"))
    assert out == {"id": "P-1", "summary": "s", "deeplink": "d"}


def test_emit_includes_folder_when_set():
    out = srv._emit(Pointer(id="P-1", summary="s", deeplink="d", folder="iCloud / Notes"))
    assert out == {"id": "P-1", "summary": "s", "deeplink": "d", "folder": "iCloud / Notes"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_contracts.py::test_pointer_folder_set tests/test_server.py::test_emit_includes_folder_when_set -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'folder'`.

- [ ] **Step 3: Add the `folder` field**

In `apple_mcp/contracts.py`, change the `Pointer` dataclass body to:

```python
    id: str
    summary: str
    deeplink: str
    folder: str | None = None  # notes_all only: "Account / Folder"; None elsewhere
```

- [ ] **Step 4: Update `_emit`**

In `apple_mcp/server.py`, replace `_emit`:

```python
def _emit(p: Pointer) -> dict[str, str]:
    d = {"id": p.id, "summary": p.summary, "deeplink": p.deeplink}
    if p.folder is not None:
        d["folder"] = p.folder
    return d
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_contracts.py tests/test_server.py -v`
Expected: PASS (all, including pre-existing tests).

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check .
git add apple_mcp/contracts.py apple_mcp/server.py tests/test_contracts.py tests/test_server.py
git commit -m "feat(notes): add optional folder field to Pointer + _emit

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `notes_all` — list every note

**Files:**
- Modify: `apple_mcp/adapters/notes.py` (add `_LIST_ALL`, `_parse_all`, `NotesAdapter.get_all`)
- Modify: `apple_mcp/server.py` (add `notes_all` tool after the `notes` tool at line 104)
- Test: `tests/test_notes.py`

**Interfaces:**
- Consumes: `Pointer(..., folder=...)` from Task 1.
- Produces: `NotesAdapter.get_all() -> list[Pointer]`; `_parse_all(raw: str) -> list[Pointer]`; tool `srv.notes_all() -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_notes.py` (append; add `_parse_all` to the existing import from `apple_mcp.adapters.notes`):

```python
from apple_mcp.adapters.notes import _parse, _parse_all  # update existing import line


def test_parse_all_id_folder_title():
    raw = (
        "x-coredata://S/ICNote/p1\tiCloud / Groceries\tMilk\n"
        "x-coredata://S/ICNote/p2\tOn My Mac / Ideas\tRocket\n"
    )
    ptrs = _parse_all(raw)
    assert len(ptrs) == 2
    assert ptrs[0].id == "x-coredata://S/ICNote/p1"
    assert ptrs[0].folder == "iCloud / Groceries"
    assert ptrs[0].summary == "Milk"
    assert ptrs[0].deeplink == ""
    assert ptrs[1].folder == "On My Mac / Ideas"


def test_parse_all_untitled():
    ptrs = _parse_all("x-coredata://S/ICNote/p3\tiCloud / Notes\t\n")
    assert ptrs[0].summary == "(untitled note)"
    assert ptrs[0].folder == "iCloud / Notes"


def test_parse_all_skips_blank():
    assert _parse_all("\n   \n") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_notes.py -v`
Expected: FAIL — `ImportError: cannot import name '_parse_all'`.

- [ ] **Step 3: Implement the AppleScript + parser + method**

In `apple_mcp/adapters/notes.py`, add after the existing `_SEARCH` constant:

```python
# notes_all: every note across accounts, excluding Recently Deleted. id+name are read in
# one multi-property snapshot ({id, name} of (notes of f)) so the two lists stay aligned —
# do NOT split into separate "id of every note" / "name of every note" events (they can
# mispair if Notes mutates between calls). Lines are built via `set end of` + a TID join to
# avoid O(n^2) string concatenation on large libraries.
# ponytail: no cap — the 30s osascript timeout is the de-facto ceiling and a too-large
# library fails whole. Add offset/limit pagination only if that bites.
_LIST_ALL = """on run argv
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
end run"""
```

Add the parser after `_parse`:

```python
def _parse_all(raw: str) -> list[Pointer]:
    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        ident = parts[0]
        folder = parts[1] if len(parts) > 1 else None
        title = parts[2] if len(parts) > 2 else ""
        out.append(
            Pointer(
                id=ident,
                summary=title.strip() or "(untitled note)",
                deeplink="",
                folder=folder,
            )
        )
    return out
```

Add the method inside `NotesAdapter` (after `get_pointers`):

```python
    def get_all(self) -> list[Pointer]:
        """Every note (excludes Recently Deleted) as account-qualified pointers.

        Folder is "Account / Folder". No cap: a very large library can exceed the
        osascript 30s timeout, in which case the whole call fails (no partial results).
        """
        return _parse_all(run_osascript(_LIST_ALL))
```

- [ ] **Step 4: Wire the tool**

In `apple_mcp/server.py`, add after the `notes` tool (after line 104):

```python
@mcp.tool()
def notes_all() -> list[dict]:
    """List every note as pointers (id + "Account / Folder" + title), excluding Recently
    Deleted. No cap; a very large library can hit the osascript timeout (all-or-nothing)."""
    return [_emit(p) for p in _notes.get_all()]
```

- [ ] **Step 5: Add the tool-dispatch test**

In `tests/test_server.py`, extend `_FakeSource` with a `get_all` method (or add to `_FakeWriter` if that is where notes is faked — use `_FakeSource`) and a test:

```python
def test_notes_all_dispatches(monkeypatch):
    class _FakeNotes:
        def get_all(self):
            return [Pointer(id="N-1", summary="Milk", deeplink="", folder="iCloud / Groceries")]

    monkeypatch.setattr(srv, "_notes", _FakeNotes())
    out = srv.notes_all()
    assert out == [{"id": "N-1", "summary": "Milk", "deeplink": "", "folder": "iCloud / Groceries"}]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_notes.py tests/test_server.py::test_notes_all_dispatches -v`
Expected: PASS.

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check .
git add apple_mcp/adapters/notes.py apple_mcp/server.py tests/test_notes.py tests/test_server.py
git commit -m "feat(notes): notes_all — list every note as account-qualified pointers

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `note_bodies` — opt-in body hydration

**Files:**
- Modify: `apple_mcp/adapters/notes.py` (add `MAX_BODIES`, `_BODIES`, `_parse_bodies`, `NotesAdapter.get_bodies`)
- Modify: `apple_mcp/server.py` (add `note_bodies` tool)
- Test: `tests/test_notes.py`, `tests/test_server.py`

**Interfaces:**
- Produces: `MAX_BODIES = 50`; `_parse_bodies(raw: str) -> list[dict]` → `[{"id": str, "body": str}]`; `NotesAdapter.get_bodies(ids: list[str]) -> list[dict]`; tool `srv.note_bodies(ids: list[str]) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_notes.py` (append; add `_parse_bodies`, `MAX_BODIES`, and `NotesAdapter` to imports):

```python
import pytest

from apple_mcp.adapters.notes import MAX_BODIES, NotesAdapter, _parse_bodies


def test_parse_bodies_basic():
    raw = "id1\x1fHello\x1eid2\x1fWorld\x1e"
    assert _parse_bodies(raw) == [
        {"id": "id1", "body": "Hello"},
        {"id": "id2", "body": "World"},
    ]


def test_parse_bodies_preserves_newlines_and_tabs():
    raw = "id1\x1fline one\nline two\tindented\x1e"
    out = _parse_bodies(raw)
    assert out == [{"id": "id1", "body": "line one\nline two\tindented"}]


def test_parse_bodies_keeps_empty_body():
    assert _parse_bodies("id1\x1f\x1e") == [{"id": "id1", "body": ""}]


def test_parse_bodies_skips_trailing_and_malformed():
    # trailing "" after final RS, and a record with no US separator, are skipped
    assert _parse_bodies("id1\x1fHi\x1emalformed\x1e") == [{"id": "id1", "body": "Hi"}]


def test_get_bodies_rejects_empty():
    with pytest.raises(ValueError, match="at least one note id"):
        NotesAdapter().get_bodies([])


def test_get_bodies_rejects_oversize():
    with pytest.raises(ValueError, match="at most 50"):
        NotesAdapter().get_bodies([f"id{i}" for i in range(MAX_BODIES + 1)])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_notes.py -v`
Expected: FAIL — `ImportError: cannot import name '_parse_bodies'`.

- [ ] **Step 3: Implement the AppleScript + parser + method**

In `apple_mcp/adapters/notes.py`, add a constant near `MAX_NOTES`:

```python
MAX_BODIES = 50
```

Add after `_LIST_ALL`:

```python
# note_bodies: opt-in, batched body hydration. plaintext contains newlines/tabs, so a
# line/tab-delimited format can't frame it — use ASCII control chars that text never
# carries: US (\x1f, character id 31) between id and body, RS (\x1e, character id 30)
# between records. A literal-text sentinel (e.g. "@@@END@@@") could appear in a body and
# corrupt parsing; control chars effectively cannot. Unknown ids are skipped (try).
_BODIES = """on run argv
  set out to ""
  tell application "Notes"
    repeat with theId in argv
      try
        set out to out & theId & (character id 31) & (plaintext of note id theId) & (character id 30)
      end try
    end repeat
  end tell
  return out
end run"""
```

Add the parser after `_parse_all`:

```python
def _parse_bodies(raw: str) -> list[dict]:
    out = []
    for record in raw.split("\x1e"):
        ident, sep, body = record.partition("\x1f")
        if not sep:  # trailing "" after final RS, or a malformed record — skip
            continue
        out.append({"id": ident.strip(), "body": body})
    return out
```

Add the method inside `NotesAdapter`:

```python
    def get_bodies(self, ids: list[str]) -> list[dict]:
        """Hydrate plaintext bodies for up to MAX_BODIES ids → [{"id", "body"}].

        Unknown ids are silently skipped; the caller diffs returned vs requested ids.
        """
        if not ids:
            raise ValueError("note_bodies needs at least one note id")
        if len(ids) > MAX_BODIES:
            raise ValueError(
                f"note_bodies accepts at most {MAX_BODIES} ids per call; "
                f"got {len(ids)} — chunk your requests"
            )
        return _parse_bodies(run_osascript(_BODIES, *ids))
```

- [ ] **Step 4: Wire the tool**

In `apple_mcp/server.py`, add after `notes_all`:

```python
@mcp.tool()
def note_bodies(ids: list[str]) -> list[dict]:
    """Hydrate plaintext bodies for up to 50 note ids (opt-in; search stays pointer-only).
    Returns [{"id", "body"}]; unknown ids are silently skipped."""
    return _notes.get_bodies(ids)
```

- [ ] **Step 5: Add the tool-dispatch test**

In `tests/test_server.py` (append):

```python
def test_note_bodies_dispatches(monkeypatch):
    class _FakeNotes:
        def get_bodies(self, ids):
            self.got = ids
            return [{"id": ids[0], "body": "B"}]

    fake = _FakeNotes()
    monkeypatch.setattr(srv, "_notes", fake)
    out = srv.note_bodies(["N-1"])
    assert fake.got == ["N-1"]
    assert out == [{"id": "N-1", "body": "B"}]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_notes.py tests/test_server.py::test_note_bodies_dispatches -v`
Expected: PASS.

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check .
git add apple_mcp/adapters/notes.py apple_mcp/server.py tests/test_notes.py tests/test_server.py
git commit -m "feat(notes): note_bodies — opt-in batched body hydration

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `delete_note` — recoverable delete with optional title guard

**Files:**
- Modify: `apple_mcp/adapters/notes.py` (add `_DELETE`, `NotesAdapter.delete`)
- Modify: `apple_mcp/server.py` (add `delete_note` tool with `@_write_tool`)
- Test: `tests/test_notes.py`, `tests/test_server.py`

**Interfaces:**
- Consumes: `run_osascript(script, *args)`.
- Produces: `NotesAdapter.delete(ident: str, expect_title: str | None = None) -> None`; tool `srv.delete_note(id: str, expect_title: str | None = None) -> dict` returning `{"deleted": id}`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_notes.py` (append):

```python
def test_delete_rejects_empty():
    with pytest.raises(ValueError, match="needs a note id"):
        NotesAdapter().delete("")


def test_delete_rejects_whitespace():
    with pytest.raises(ValueError, match="needs a note id"):
        NotesAdapter().delete("   ")


def test_delete_passes_id_and_title(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "apple_mcp.adapters.notes.run_osascript",
        lambda script, *args: calls.append(args) or "",
    )
    NotesAdapter().delete("N-1", expect_title="Milk")
    assert calls == [("N-1", "Milk")]


def test_delete_without_title_passes_only_id(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "apple_mcp.adapters.notes.run_osascript",
        lambda script, *args: calls.append(args) or "",
    )
    NotesAdapter().delete("N-1")
    assert calls == [("N-1",)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_notes.py -k delete -v`
Expected: FAIL — `AttributeError: 'NotesAdapter' object has no attribute 'delete'`.

- [ ] **Step 3: Implement the AppleScript + method**

In `apple_mcp/adapters/notes.py`, add after `_BODIES`:

```python
# delete_note: moves the note to Recently Deleted (recoverable ~30 days). Notes ids are
# x-coredata:// URLs that embed the store id → globally unique, so delete-by-id targets
# exactly one note. expect_title (optional argv[2]) guards against stale/wrong ids: the
# script errors before deleting if the live title doesn't match.
_DELETE = """on run argv
  tell application "Notes"
    set n to note id (item 1 of argv)
    if (count of argv) > 1 then
      if (name of n) is not (item 2 of argv) then error "note title does not match expect_title"
    end if
    delete n
  end tell
end run"""
```

Add the method inside `NotesAdapter`:

```python
    def delete(self, ident: str, expect_title: str | None = None) -> None:
        """Delete a note by id → Recently Deleted (recoverable). Content-verify first.

        When expect_title is given, the note is deleted only if its current title matches.
        """
        if not ident.strip():
            raise ValueError("delete_note needs a note id")
        if expect_title is not None:
            run_osascript(_DELETE, ident, expect_title)
        else:
            run_osascript(_DELETE, ident)
```

- [ ] **Step 4: Wire the tool**

In `apple_mcp/server.py`, add near `delete_event` (after it, with the other `@_write_tool` tools):

```python
@_write_tool
def delete_note(id: str, expect_title: str | None = None) -> dict:
    """Delete a note by id → Recently Deleted (recoverable ~30 days). Destructive.
    Pass expect_title to verify the target before deleting (content-verify first)."""
    _notes.delete(id, expect_title)
    return {"deleted": id}
```

- [ ] **Step 5: Add the tool-dispatch test**

In `tests/test_server.py` (append):

```python
def test_delete_note_dispatches(monkeypatch):
    class _FakeNotes:
        def __init__(self):
            self.calls = []

        def delete(self, ident, expect_title=None):
            self.calls.append((ident, expect_title))

    fake = _FakeNotes()
    monkeypatch.setattr(srv, "_notes", fake)
    out = srv.delete_note("N-1", expect_title="Milk")
    assert fake.calls == [("N-1", "Milk")]
    assert out == {"deleted": "N-1"}
```

Note: `srv.delete_note` exists only when not in read-only mode. The default test env is not read-only, so the attribute is present. (Read-only registration is already covered by the existing `test_read_only_*` tests.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_notes.py tests/test_server.py::test_delete_note_dispatches -v`
Expected: PASS.

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check .
git add apple_mcp/adapters/notes.py apple_mcp/server.py tests/test_notes.py tests/test_server.py
git commit -m "feat(notes): delete_note — recoverable delete with optional title guard

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Integration coverage (real Notes.app, manual)

**Files:**
- Modify: `tests/test_integration.py`

**Interfaces:**
- Consumes: `NotesAdapter.get_all`, `get_bodies`, `delete` from Tasks 2–4.

These tests touch the live Notes.app and need Automation (TCC) permission. They are `@pytest.mark.integration` and run manually (`uv run pytest -m integration`), never in CI. They exist to guard the two things unit tests can't: that the AppleScript actually runs, and that control-char delimiters survive `osascript` → Python byte-for-byte (spec amendment #5). They also validate the `{id, name} of (notes of f)` snapshot returns aligned parallel lists (and exercise the single-note-per-folder shape, the known AppleScript list-coercion quirk).

- [ ] **Step 1: Add the integration tests**

In `tests/test_integration.py` (append; imports inside the function follow the file's existing per-test import style):

```python
@pytest.mark.integration
def test_notes_all_and_bodies_and_delete_roundtrip():
    """Create a note with newlines+tabs, find it via get_all, hydrate its body
    byte-for-byte, then delete it with a matching expect_title."""
    from apple_mcp.adapters.notes import NotesAdapter, _BODIES, _LIST_ALL  # noqa: F401
    from apple_mcp.runtime import run_osascript

    notes = NotesAdapter()
    title = "apple-mcp-itest-note"
    body_marker = "line one\nline two\tindented\nline three"

    # create a note via osascript (test-only helper; not part of the shipped surface)
    create = (
        'on run argv\n'
        '  tell application "Notes"\n'
        '    make new note at folder "Notes" of account 1 '
        'with properties {name:(item 1 of argv), body:(item 2 of argv)}\n'
        '  end tell\n'
        'end run'
    )
    run_osascript(create, title, body_marker)

    try:
        # get_all finds it, with an account-qualified folder
        all_ptrs = notes.get_all()
        mine = [p for p in all_ptrs if p.summary == title]
        assert mine, "created note not returned by get_all"
        ptr = mine[0]
        assert ptr.folder and " / " in ptr.folder  # "Account / Folder"

        # body hydrates byte-for-byte (newlines + tabs survive the control-char framing)
        bodies = notes.get_bodies([ptr.id])
        assert len(bodies) == 1 and bodies[0]["id"] == ptr.id
        assert "line two\tindented" in bodies[0]["body"]
        assert "line one\nline two" in bodies[0]["body"]

        # mismatched expect_title refuses to delete
        with pytest.raises(RuntimeError):
            notes.delete(ptr.id, expect_title="wrong title")
        assert any(p.summary == title for p in notes.get_all())

        # matching expect_title deletes (moves to Recently Deleted)
        notes.delete(ptr.id, expect_title=title)
        assert not any(p.summary == title for p in notes.get_all())
    finally:
        # best-effort cleanup if an assertion left the note behind
        for p in notes.get_all():
            if p.summary == title:
                notes.delete(p.id)
```

- [ ] **Step 2: Run the integration test manually**

Run: `uv run pytest tests/test_integration.py::test_notes_all_and_bodies_and_delete_roundtrip -m integration -v`
Expected: PASS (grant Automation permission for the test runner to control Notes if prompted). If `make new note ... of account 1` fails on this machine's Notes setup, adjust the target folder/account in the create helper — it is test scaffolding only.

- [ ] **Step 3: Confirm unit suite + lint still clean**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: PASS (integration tests are deselected by default).

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test(notes): integration round-trip for notes_all/note_bodies/delete_note

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Pointer.folder + _emit → Task 1. ✓
- notes_all (no cap, account-qualified, atomic fetch #1/#2, TID join #3) → Task 2. ✓
- note_bodies (control-char delimiters #5, MAX_BODIES=50, validation) → Task 3. ✓
- delete_note (@_write_tool, expect_title #4, recoverable) → Task 4. ✓
- Integration round-trip incl. delimiter byte-fidelity (#5) → Task 5. ✓
- Known limitations (localized "Recently Deleted", no-cap timeout, delimiter) → documented in code comments (Task 2/3) and the spec; no code task needed.
- "Pointers, not payload" invariant: `notes()` untouched; `note_bodies` is the explicit payload call. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command has expected output. ✓

**Type consistency:** `get_all() -> list[Pointer]`, `get_bodies(ids: list[str]) -> list[dict]`, `delete(ident, expect_title=None) -> None`, `_parse_all`, `_parse_bodies`, `MAX_BODIES`, tool returns (`notes_all`→list[dict], `note_bodies`→list[dict], `delete_note`→`{"deleted": id}`) are consistent across tasks and match the spec. ✓
