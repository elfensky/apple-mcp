# mac-mcp Rebrand + First Public Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the project `apple-mcp → mac-mcp` end-to-end and ship it publicly to PyPI via a TestPyPI→PyPI Trusted-Publishing pipeline mirroring `../lintle`.

**Architecture:** First flip the git flow to lintle's model — `develop` becomes the trunk, `main` becomes release-only (Task 0). Then five phases: (1) rename the Python package, (2) packaging + LICENSE, (3) publish workflow mirroring lintle, (4) GitHub repo rename, (5) cut the release by bootstrapping a release-only `main` from `develop`'s tip with a `commit-tree` merge commit — pushing `main` is the release act (push-to-`main` auto-publishes to TestPyPI).

**Tech Stack:** Python ≥3.11, FastMCP 2.0, PyObjC/EventKit (macOS-only), `uv`, hatchling, ruff, pytest, GitHub Actions, PyPI Trusted Publishing (OIDC).

## Global Constraints

- **Git flow (lintle model):** `develop` is the trunk (full history); `main` is release-only (one `commit-tree` merge commit per release, never committed to directly). Established in Task 0.
- All Phase 1–4 work happens on a feature branch `feat/rebrand-mac-mcp` off **`develop`**, PR'd back into `develop` (rebase-and-merge, keeping `develop` linear). `main` is touched only by the release bootstrap in Task 5 — and pushing it triggers a TestPyPI publish.
- **No backfill:** apple-mcp never published `v0.1.0`–`v0.1.2` to PyPI, so the old tags stay as-is on `develop`'s history; `main` starts fresh at `v0.2.0`. Do NOT rebuild old tags/releases (unlike lintle, which had PyPI artifacts to preserve). Repo root (shared anchor) is `e6582e2`.
- Distribution + repo + import + binary + env var all become `mac-mcp` / `mac_mcp` / `MAC_MCP`.
- Version: `0.1.2` → `0.2.0`.
- License: MIT, `license = "MIT"` SPDX + `license-files = ["LICENSE"]`. **No** `License ::` classifier (PEP 639 redundancy).
- Author: `{ name = "Andrei Lavrenov", email = "andrei@lav.ren" }`.
- **Protected strings — NEVER rename** (third-party prior art / frozen history):
  - `supermemoryai/apple-mcp`, `griches/apple-mcp`, `Dhravya/apple-mcp` and the markdown link `[apple-mcp](https://github.com/supermemoryai/apple-mcp)` and `[apple-mcp / per-app servers](https://github.com/griches/apple-mcp)` in `CREDITS.md`.
  - The `supermemoryai/apple-mcp` reference in `DESIGN.md:11`.
  - All existing dated entries in `CHANGELOG.md` (history is immutable — the rename is a NEW entry).
  - `docs/superpowers/plans/2026-06-28-notes-surface.md` and `docs/superpowers/specs/2026-06-28-notes-surface-design.md` (frozen historical build artifacts — leave verbatim, incl. `elfensky/apple-mcp#40`).
- Verification gate after any code/packaging change: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`. (macOS host — PyObjC won't `uv sync` on Linux.)

---

### Task 0: Flip the trunk to `develop`, then branch off it

**Files:** none (git/GitHub only)

**Interfaces:**
- Produces: GitHub repo renamed `elfensky/mac-mcp`; `develop` = trunk + default branch; remote `main` deleted (re-created release-only in Task 5); feature branch `feat/rebrand-mac-mcp` off `develop`.

Pre-flight already verified: no branch protection on `main`, no open PRs, default branch is `main`, tags `v0.1.0/v0.1.1/v0.1.2` exist, GitHub releases exist for `v0.1.0`/`v0.1.2`.

**Why rename the GitHub repo now (not in Task 5):** PyPI Trusted Publishing matches the OIDC token's `repository` claim against the registered publisher (`elfensky/mac-mcp`). The repo must already be named `mac-mcp` before the first `main` push that triggers a publish, or the publish is rejected. Renaming here makes every later `gh`/remote command consistently `mac-mcp` too.

- [ ] **Step 1: Confirm clean working tree and you are on `main`**

```bash
git status --short && git rev-parse --abbrev-ref HEAD
```
Expected: no output from `status` (clean), branch is `main`.

- [ ] **Step 2: Rename the GitHub repo and point the remote at it**

```bash
gh repo rename mac-mcp --repo elfensky/apple-mcp --yes
git remote set-url origin https://github.com/elfensky/mac-mcp.git
git remote -v   # confirm origin -> elfensky/mac-mcp
```
(GitHub auto-redirects the old URL, so nothing breaks in the meantime.)

- [ ] **Step 3: Rename the local trunk and push `develop`**

```bash
git branch -m main develop
git push -u origin develop
```

- [ ] **Step 4: Set `develop` as the GitHub default branch**

```bash
gh repo edit elfensky/mac-mcp --default-branch develop
```
Expected: succeeds. Verify: `gh repo view elfensky/mac-mcp --json defaultBranchRef -q .defaultBranchRef.name` → `develop`.

- [ ] **Step 5: Delete the old remote `main`**

```bash
git push origin --delete main
```
Expected: deleted. (Tags `v0.1.*` and the `v0.1.0`/`v0.1.2` GitHub releases are bound to tags, not the branch — they survive. Verify: `gh release list -R elfensky/mac-mcp` still lists them.)

- [ ] **Step 6: Create the feature branch off `develop`**

```bash
git checkout -b feat/rebrand-mac-mcp
```

- [ ] **Step 7: Confirm clean baseline**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass (the green state we must preserve through the rename).

---

### Task 1: Rename the Python package + code identifiers

**Files:**
- Rename: `apple_mcp/` → `mac_mcp/` (directory, via `git mv`)
- Modify: every `*.py` under `mac_mcp/` and `tests/` (imports, server name, env var, logger, prose strings)

**Interfaces:**
- Produces: import root `mac_mcp` (was `apple_mcp`); FastMCP server name `"mac-mcp"`; env var `MAC_MCP_READ_ONLY`; console-script target `mac_mcp:main` (wired in Task 2). All later tasks and docs reference these.

Every `apple_mcp` / `apple-mcp` / `APPLE_MCP` token in `.py` files is **ours** (no third-party Python package by those names is imported), so a blanket replace across `.py` is safe. The protected third-party strings live only in Markdown, handled in Task 4.

- [ ] **Step 1: Rename the package directory**

```bash
git mv apple_mcp mac_mcp
```

- [ ] **Step 2: Replace identifiers in all Python sources**

```bash
# All three tokens in .py files refer to our project — safe to replace wholesale.
grep -rIl --include='*.py' -E 'apple_mcp|apple-mcp|APPLE_MCP' mac_mcp tests \
  | xargs sed -i '' -e 's/apple_mcp/mac_mcp/g' -e 's/apple-mcp/mac-mcp/g' -e 's/APPLE_MCP/MAC_MCP/g'
```

This updates, among others:
- `mac_mcp/server.py:31` → `mcp = FastMCP("mac-mcp")`
- `mac_mcp/server.py:53` → `os.environ.get("MAC_MCP_READ_ONLY", "")` (+ docstrings at lines 3, 52)
- `mac_mcp/runtime.py:202` → `logging.getLogger("mac_mcp")` (+ prose at lines 67, 69, 254)
- `mac_mcp/adapters/shortcuts.py:66` → `prefix="mac-mcp-shortcut-"`
- `mac_mcp/__init__.py`, `mac_mcp/__main__.py` (module docstring `python -m mac_mcp`)
- all `from mac_mcp...import` lines across `tests/*.py`

- [ ] **Step 3: Verify nothing in Python still says apple**

Run: `grep -rIn --include='*.py' -E 'apple_mcp|apple-mcp|APPLE_MCP' mac_mcp tests; echo "exit=$?"`
Expected: no matches (grep prints nothing, `exit=1`).

- [ ] **Step 4: Point pyproject at the renamed package, then re-sync**

The editable install still maps the old `apple_mcp` dir, so tests can't import `mac_mcp` until pyproject's package-pointing lines are updated. Edit `pyproject.toml`:

```toml
[project.scripts]
mac-mcp = "mac_mcp:main"
```

```toml
[tool.hatch.build.targets.wheel]
packages = ["mac_mcp"]
```

(Leave `name = "apple-mcp"` and `version`/metadata alone here — Task 2 handles the distribution identity. Only the two package-pointing lines change now.) Then re-sync the editable install:

Run: `uv sync`
Expected: succeeds (re-installs the package from `mac_mcp/`).

- [ ] **Step 5: Run the full gate**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass. (Tests import `mac_mcp` now; the rename is behavior-preserving.)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: rename package apple_mcp -> mac_mcp (server, env var, imports)"
```

---

### Task 2: Packaging metadata, LICENSE, version bump

**Files:**
- Modify: `pyproject.toml` (`[project]` block, `[project.scripts]`, `[tool.hatch.build.targets.wheel]`, add `[[tool.uv.index]]`)
- Create: `LICENSE`
- Regenerate: `uv.lock`

**Interfaces:**
- Consumes: package dir `mac_mcp/`, entry point `mac_mcp:main` (from Task 1).
- Produces: distribution name `mac-mcp` v`0.2.0`, console script `mac-mcp`, `testpypi` named index (consumed by Task 3's workflow).

- [ ] **Step 1: Rewrite the `[project]` block**

Replace the existing `[project]` block in `pyproject.toml` (currently `name = "apple-mcp"` … through `dependencies = [...]`) with:

```toml
[project]
name = "mac-mcp"
version = "0.2.0"
description = "One consolidated MCP server for native macOS apps (Calendar, Reminders, Mail, ...)."
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
license-files = ["LICENSE"]
authors = [{ name = "Andrei Lavrenov", email = "andrei@lav.ren" }]
keywords = [
    "mcp",
    "model-context-protocol",
    "macos",
    "apple",
    "eventkit",
    "calendar",
    "reminders",
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: MacOS X",
    "Intended Audience :: Developers",
    "Operating System :: MacOS",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Utilities",
]
dependencies = [
    "fastmcp>=2.0",
    "pyobjc-framework-EventKit>=10.0",    # Calendar + Reminders (v1)
]
```

(Keep the two explanatory comments that follow the dependencies in the current file — the Contacts/Photos notes.)

- [ ] **Step 2: Add the TestPyPI index (scripts + wheel target already point at `mac_mcp` from Task 1)**

`[project.scripts]` (`mac-mcp = "mac_mcp:main"`) and `[tool.hatch.build.targets.wheel]` (`packages = ["mac_mcp"]`) were set in Task 1 Step 4 — confirm they read:

```toml
[project.scripts]
mac-mcp = "mac_mcp:main"
```

```toml
[tool.hatch.build.targets.wheel]
packages = ["mac_mcp"]
```

And append (mirrors `../lintle`):

```toml
# TestPyPI as a named publish target. `explicit = true` keeps it out of normal
# dependency resolution — it is only ever used via `uv publish --index testpypi`.
[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
publish-url = "https://test.pypi.org/legacy/"
explicit = true
```

- [ ] **Step 3: Create the LICENSE file**

Create `LICENSE` with the standard MIT text:

```
MIT License

Copyright (c) 2026 Andrei Lavrenov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Regenerate the lockfile under the new name**

Run: `uv sync`
Expected: succeeds; `uv.lock` now lists `name = "mac-mcp"`. Verify: `grep -m1 'name = "mac-mcp"' uv.lock`.

- [ ] **Step 5: Build and verify the artifacts are renamed**

Run: `uv build`
Expected: `dist/mac_mcp-0.2.0-py3-none-any.whl` and `dist/mac_mcp-0.2.0.tar.gz` are produced (pure-Python wheel). Verify: `ls dist/ | grep mac_mcp-0.2.0`.

- [ ] **Step 6: Confirm the gate still passes**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml LICENSE uv.lock
git commit -m "build: rename distribution to mac-mcp 0.2.0, add MIT license + metadata + TestPyPI index"
```

---

### Task 3: Publish workflow (mirror lintle) + CI string update

**Files:**
- Create: `.github/workflows/publish.yml`
- Modify: `.github/workflows/ci.yml` (only any `apple_mcp`/`apple-mcp` string; structure unchanged)

**Interfaces:**
- Consumes: the `testpypi` index and `mac-mcp` name from Task 2.
- Produces: push-to-`main` → TestPyPI, `workflow_dispatch target=pypi` → PyPI.

This mirrors `../lintle/.github/workflows/publish.yml` verbatim except: runner is `macos-latest` (PyObjC can't `uv sync` on Linux) and URLs point at `mac-mcp`.

- [ ] **Step 1: Create `.github/workflows/publish.yml`**

```yaml
name: Publish

# Two triggers, one workflow:
#   - push to main      -> auto-publish to TestPyPI
#   - workflow_dispatch -> pick target manually (testpypi or pypi)
#
# Production PyPI stays gated behind manual dispatch — uploads are permanent
# and `target=pypi` should be a deliberate human action. Trusted Publishing
# (OIDC) handles auth for both indexes — no API tokens stored.
#
# Runner is macos-latest (not lintle's ubuntu): PyObjC/EventKit are macOS-only,
# so `uv sync` + pytest can't run on Linux. The built wheel is still pure-Python.
#
# `main` is release-only (develop is the trunk), so a push to main is a
# per-release event — the TestPyPI publish never fires on ordinary feature work.

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      target:
        description: "Where to publish"
        type: choice
        options:
          - testpypi
          - pypi
        default: testpypi

jobs:
  publish:
    runs-on: macos-latest
    environment:
      name: pypi
      url: ${{ inputs.target == 'pypi' && 'https://pypi.org/project/mac-mcp/' || 'https://test.pypi.org/project/mac-mcp/' }}
    permissions:
      id-token: write # required for Trusted Publishing (OIDC)
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Verify before publishing
        run: |
          uv sync --locked
          uv run pytest
          uv run ruff check .
          uv run ruff format --check .

      - name: Build sdist and wheel
        run: uv build

      # inputs.target is unset on push events, so a push to main lands here.
      - name: Publish to TestPyPI
        if: github.event_name == 'push' || inputs.target == 'testpypi'
        run: uv publish --index testpypi --trusted-publishing always

      # PyPI only on explicit dispatch — never on a push event.
      - name: Publish to PyPI
        if: github.event_name == 'workflow_dispatch' && inputs.target == 'pypi'
        run: uv publish --trusted-publishing always
```

- [ ] **Step 2: Update ci.yml triggers + scrub any apple string**

In `.github/workflows/ci.yml`, change the push trigger to cover both trunk and release branch:

```yaml
on:
  push:
    branches: [develop, main]
  pull_request:
```

Then scrub any apple identifier:

```bash
grep -n -E 'apple_mcp|apple-mcp|APPLE_MCP' .github/workflows/ci.yml || echo "none"
```

If matches appear, replace `apple_mcp`→`mac_mcp` / `apple-mcp`→`mac-mcp` / `APPLE_MCP`→`MAC_MCP`. (Structure — macos-latest, lint-gated pytest — stays.)

- [ ] **Step 3: Validate the workflow YAML parses**

Run: `python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in ('.github/workflows/publish.yml','.github/workflows/ci.yml')]; print('yaml ok')"`
Expected: `yaml ok`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/publish.yml .github/workflows/ci.yml
git commit -m "ci: add TestPyPI->PyPI publish workflow (mirrors lintle, macos runner)"
```

---

### Task 4: Targeted documentation rename

**Files:**
- Modify (our-project refs only): `README.md`, `DESIGN.md`, `CONTRIBUTING.md`, `CLAUDE.md`, `CREDITS.md`, `CHANGELOG.md` (intro line only), `docs/parity-checklist.md`, `docs/projection-contract.md`

**Interfaces:** none (docs).

Per Global Constraints, the protected third-party strings must survive. Do NOT blanket-sed Markdown.

- [ ] **Step 1: Rename our-project refs in the safe docs**

These files contain only our-project references (no third-party `apple-mcp`):

```bash
for f in README.md CONTRIBUTING.md CLAUDE.md docs/parity-checklist.md docs/projection-contract.md; do
  sed -i '' -e 's/apple_mcp/mac_mcp/g' -e 's/apple-mcp/mac-mcp/g' -e 's/APPLE_MCP/MAC_MCP/g' "$f"
done
```

Then update the tracker reference in `CLAUDE.md` (the life-cockpit line): `elfensky/apple-mcp` → `elfensky/mac-mcp` (already covered by the `apple-mcp`→`mac-mcp` replace above — verify it landed).

- [ ] **Step 2: Hand-edit DESIGN.md (one protected line)**

In `DESIGN.md`, replace our-project `apple-mcp`/`APPLE_MCP` references with `mac-mcp`/`MAC_MCP`, **except line 11** which names the third-party `supermemoryai/apple-mcp` — leave that token verbatim. Recommended: do it by eye, then verify:

```bash
grep -n 'supermemoryai/apple-mcp' DESIGN.md   # must still be present (1 hit, line ~11)
grep -nc 'mac-mcp' DESIGN.md                   # our refs now renamed
```

- [ ] **Step 3: Hand-edit CREDITS.md (mixed file)**

`CREDITS.md` mixes our self-references (rename) with third-party names (protect). Change every `apple-mcp` that refers to **our** project (e.g. "apple-mcp stands on…", "apple-mcp re-implements…", "apple-mcp learned…", "apple-mcp's Apple Mail adapter", "apple-mcp's only planned code port") to `mac-mcp`. Leave verbatim:
- `[apple-mcp](https://github.com/supermemoryai/apple-mcp)` and the words "by Dhravya Shah"
- `Dhravya/apple-mcp`
- `[apple-mcp / per-app servers](https://github.com/griches/apple-mcp)`
- `` `griches/apple-mcp` ``

Verify the protected strings survived:

```bash
grep -c -E 'supermemoryai/apple-mcp|griches/apple-mcp|Dhravya/apple-mcp' CREDITS.md  # expect 3+
```

- [ ] **Step 4: Update only the CHANGELOG intro, not history**

In `CHANGELOG.md`, change the single intro sentence "All notable changes to apple-mcp are documented here." → "…to mac-mcp…". Leave every dated `## [x.y.z]` entry (incl. the `APPLE_MCP_READ_ONLY` mentions in 0.1.1/0.1.0 history) **unchanged** — they were accurate at the time. (The new 0.2.0 entry is added in Task 5.)

- [ ] **Step 5: Document the branching & release contract in CONTRIBUTING.md**

Add this section to `CONTRIBUTING.md` after the conventional-commits line (the one ending `…`refactor:`).`):

```markdown

## Branching & releases

- **`develop`** is the trunk — all history lives here. Branch features off it
  (`feature/<desc>`, `refactor/<desc>`) and PR back with **rebase-and-merge** so
  `develop` stays linear.
- **`main`** is release-only: one merge commit per release, its tree equal to
  `develop`'s release-point tree and its second parent the `develop` commit it was
  cut from. Never commit directly to `main`. `git log --first-parent main` shows the
  release timeline. Releases are annotated tags on `main`.
- **Cut a release:** bump the version + dated `CHANGELOG.md` section on `develop`,
  then build the `main` release commit (`git commit-tree`, tree from `develop`'s tip,
  parents `[previous main commit, develop tip]`), tag it `vX.Y.Z`, and push `main` —
  which triggers the TestPyPI publish. Promote to PyPI via the `publish.yml`
  `workflow_dispatch` (`target=pypi`).
```

- [ ] **Step 6: Verify no stray our-project refs remain in docs**

```bash
grep -rIn -E 'apple_mcp|APPLE_MCP' README.md DESIGN.md CONTRIBUTING.md CLAUDE.md docs/parity-checklist.md docs/projection-contract.md; echo "exit=$?"
```
Expected: no matches (`exit=1`). (`apple-mcp` may still legitimately appear only as protected third-party strings in CREDITS.md / DESIGN.md:11.)

- [ ] **Step 7: Commit**

```bash
git add README.md DESIGN.md CONTRIBUTING.md CLAUDE.md CREDITS.md CHANGELOG.md docs/parity-checklist.md docs/projection-contract.md
git commit -m "docs: rebrand apple-mcp -> mac-mcp + document develop/main release flow"
```

---

### Task 5: Cut the release (land on `develop`, bootstrap release-only `main`)

**Files:**
- Modify: `CHANGELOG.md` (new `## [0.2.0]` entry)
- Git: feature branch → `develop` (PR); `develop` → `main` (bootstrap via `commit-tree`); tag + GitHub release
- Manual (web UI): PyPI/TestPyPI trusted-publisher registration

**Interfaces:**
- Consumes: `publish.yml` + `testpypi` index (Tasks 2–3); repo already named `mac-mcp` (Task 0).

**MANUAL PREREQUISITES — do these in the web UI before pushing `main` (Step 4):**
1. **TestPyPI** (test.pypi.org → Account → Publishing → Add a pending publisher): PyPI project name `mac-mcp`, owner `elfensky`, repository `mac-mcp`, workflow filename `publish.yml`, environment `pypi`.
2. **PyPI** (pypi.org → same): identical pending publisher.

Without these, the publish steps fail with an OIDC trust error. The repo is already `elfensky/mac-mcp` (Task 0), so the OIDC `repository` claim will match.

- [ ] **Step 1: Add the 0.2.0 CHANGELOG entry (on the feature branch)**

Prepend below the intro, above `## [0.1.2]`:

```markdown
## [0.2.0] - 2026-06-29

### Changed

- **Renamed `apple-mcp` → `mac-mcp`** across the board: the PyPI distribution
  (`mac-mcp`, the `apple-mcp` name being taken by an unrelated project), the
  GitHub repo (`elfensky/mac-mcp`), the import package (`mac_mcp`), the console
  script (`mac-mcp`), and the FastMCP server name. The read-only guard env var
  is now **`MAC_MCP_READ_ONLY`** (was `APPLE_MCP_READ_ONLY`) — no backward-compat
  alias, as there were no public installs before this release.
- **Git flow** moved to `develop` (trunk) + release-only `main`, mirroring the
  sibling repos.

### Added

- **First public release on PyPI** (`uvx mac-mcp`), published via a
  TestPyPI→PyPI Trusted-Publishing pipeline. MIT `LICENSE` and full packaging
  metadata (authors, keywords, classifiers, project URLs).
```

- [ ] **Step 2: Commit and land the rebrand on `develop`**

```bash
git add CHANGELOG.md
git commit -m "release: mac-mcp 0.2.0 — rename + first public release"
git push -u origin feat/rebrand-mac-mcp
gh pr create --fill --base develop
```

After CI is green, merge the PR into `develop` with **rebase-and-merge** (`gh pr merge --rebase --delete-branch`). This does NOT publish — `develop` isn't a publish trigger.

- [ ] **Step 3: Bootstrap the release-only `main` from `develop`'s tip**

Run from a clean checkout of the updated `develop`:

```bash
git checkout develop && git pull

ROOT=$(git rev-parse e6582e2)             # shared repo root (visualization anchor)
DEV_TIP=$(git rev-parse develop)          # the 0.2.0 release point
TREE=$(git rev-parse develop^{tree})      # tree published to PyPI, by construction

# Release commit: tree from develop's tip; parents = [root, develop tip].
# (First release on main, so first parent is the shared root, not a prior main commit.)
COMMIT=$(git commit-tree "$TREE" -p "$ROOT" -p "$DEV_TIP" -m "Release v0.2.0")
[ "$(git rev-parse ${COMMIT}^{tree})" = "$TREE" ] || { echo "tree mismatch — abort"; exit 1; }

git branch main "$COMMIT"
git tag -a v0.2.0 "$COMMIT" -m "Release v0.2.0"   # tag stays local until the publish is confirmed
```

Verify the release-only view: `git log --oneline --first-parent main` → `Release v0.2.0` then the root commit.

- [ ] **Step 4: Push `main` → triggers the TestPyPI publish**

```bash
git push origin main
gh run watch    # or the Actions tab
```
Expected: the `Publish` workflow runs on `macos-latest`; `Publish to TestPyPI` step green.

Smoke-test (the server is a blocking stdio process — boot under a timeout; a clean timeout means it imported and started without crashing):

```bash
timeout 6 uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ --from mac-mcp mac-mcp; \
  [ $? -eq 124 ] && echo "booted ok (timed out as expected)" || echo "CHECK: exited early — inspect output above"
```
Expected: `booted ok` (no Python import/traceback before the timeout).

- [ ] **Step 5: Promote to production PyPI**

```bash
gh workflow run publish.yml -f target=pypi
gh run watch
```
Expected: `Publish to PyPI` step green; `mac-mcp 0.2.0` visible at https://pypi.org/project/mac-mcp/.

- [ ] **Step 6: Push the tag + cut the GitHub Release**

```bash
git push origin v0.2.0
gh release create v0.2.0 --title "mac-mcp 0.2.0" --notes "First public release. Renamed apple-mcp -> mac-mcp (PyPI: mac-mcp). See CHANGELOG.md."
```

- [ ] **Step 7: Final smoke test from production PyPI**

```bash
timeout 6 uvx mac-mcp; [ $? -eq 124 ] && echo "booted ok" || echo "CHECK: exited early"
```
Expected: `booted ok` (installs from production PyPI and the server boots).

(Out-of-repo follow-up: update the life-cockpit vault tracker `elfensky/apple-mcp → elfensky/mac-mcp`. Release complete.)

---

## Self-Review

- **Spec coverage:** Phase 0 (flip trunk + repo rename) → Task 0; Phase 1 → Task 1; Phase 2 → Task 2; Phase 3 → Task 3; Phase 4 (repo rename) → folded into Task 0 (OIDC ordering); Phase 5 → Task 5. License/metadata/PEP-639 → Task 2. TestPyPI index + lintle mirror + macos runner + release-only-main → Task 3. Branching docs → Task 4 Step 5. Protected-strings rule → Global Constraints + Task 4. Trusted-publisher manual prereq (both indexes) → Task 5. `commit-tree` bootstrap (no backfill) → Task 5 Step 3. ✓
- **Placeholders:** none — every step has exact commands/code.
- **Type/name consistency:** `mac_mcp` (import), `mac-mcp` (dist/binary/server/repo), `MAC_MCP_READ_ONLY` (env), `mac_mcp:main` (entry point) consistent across Tasks 1–3 and the workflow. Git flow (`develop` trunk, release-only `main`, `commit-tree` parents `[root, develop tip]`) consistent across Task 0, Task 4 docs, and Task 5.
