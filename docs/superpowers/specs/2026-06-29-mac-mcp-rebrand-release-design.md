# mac-mcp — rebrand + first public release

**Status:** approved (design) · **Date:** 2026-06-29 · **Owner:** elfensky

Rename the project `apple-mcp → mac-mcp` end-to-end and publish it for public access: PyPI
distribution `mac-mcp`, automated release on `v*` tag via PyPI Trusted Publishing, and a GitHub
Release per tag. The PyPI name `apple-mcp` is owned by an unrelated project (`dev-hitesh-gupta`),
which forces a distribution rename; the user chose to migrate **all** naming for consistency.

## Decisions (locked)

| Axis | Decision |
|------|----------|
| PyPI distribution name | `mac-mcp` (verified available 2026-06-29) |
| GitHub repo | `elfensky/apple-mcp` → `elfensky/mac-mcp` (rename, auto-redirects) |
| Code rename depth | **Full** — `apple_mcp/` → `mac_mcp/`, every import, the console script, the FastMCP server name, and the env var |
| Env var | `APPLE_MCP_READ_ONLY` → `MAC_MCP_READ_ONLY`, **no** backward-compat alias (zero public users pre-release — YAGNI) |
| License | MIT, © 2026 Andrei Lavrenov |
| Publish mechanism | Automated on `v*` tag: build → PyPI Trusted Publishing (OIDC, no stored tokens) → GitHub Release with notes from CHANGELOG |
| Version | `0.1.2` → `0.2.0` (rename is notable; project is pre-1.0 so a minor bump) |

## The one non-mechanical hazard: not every `apple-mcp` string is ours

`CREDITS.md` and `CHANGELOG.md` reference **other projects** literally named `apple-mcp`:
`supermemoryai/apple-mcp` (Dhravya Shah), `griches/apple-mcp` (Gary Riches),
`Dhravya/apple-mcp`. A repo-wide `sed 's/apple-mcp/mac-mcp/g'` would corrupt prior-art
attribution and rewrite those GitHub URLs into 404s.

**Rule:** the rename is *targeted*, not global.
- Rename only references to **our** project (the package, the binary, the server, our repo URL,
  our prose self-references).
- Leave third-party project names and their `github.com/<owner>/apple-mcp` URLs **verbatim**.
- Treat `CHANGELOG.md` history as immutable: dated entries describing past releases of "apple-mcp"
  stay as written (they were accurate then). The rename is recorded as a **new** `0.2.0` entry, not
  by editing the past.

Every file touched in Phase 1 is reviewed by hand against this rule — no unattended global replace.

## Migration surface (measured 2026-06-29)

- `apple_mcp` appears in **23** files; `apple-mcp` in **17**; `APPLE_MCP_READ_ONLY` in **7**.
- Package: `apple_mcp/` (`__init__.py`, `__main__.py`, `server.py`, `runtime.py`, `contracts.py`)
  + `apple_mcp/adapters/` (10 modules).
- Tests: 14 `tests/test_*.py` files import `apple_mcp`.
- Docs: `README.md`, `DESIGN.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `CREDITS.md`, `CHANGELOG.md`,
  `docs/parity-checklist.md`, `docs/projection-contract.md`.
- Build/CI: `pyproject.toml`, `.github/workflows/ci.yml`.
- Known anchor points: `apple_mcp/server.py:31` `mcp = FastMCP("apple-mcp")`; `server.py:51-53`
  the `_read_only()` env lookup; `pyproject.toml` `[project.scripts]` and
  `[tool.hatch.build.targets.wheel]`.

## Work breakdown

### Phase 1 — Code rename (mechanical, hand-verified)
- `git mv apple_mcp mac_mcp` (preserves history).
- Update every `import apple_mcp` / `from apple_mcp...` → `mac_mcp` across `mac_mcp/` and `tests/`.
- `FastMCP("apple-mcp")` → `FastMCP("mac-mcp")`.
- `APPLE_MCP_READ_ONLY` → `MAC_MCP_READ_ONLY` (lookup in `server.py` + its docstring + every test
  that sets it + every doc that mentions it).
- Apply the targeted-rename rule to docs (README, DESIGN, CONTRIBUTING, CLAUDE.md, parity-checklist,
  projection-contract), leaving prior-art names in CREDITS/CHANGELOG untouched.

### Phase 2 — Packaging + license
- `pyproject.toml`:
  - `name = "mac-mcp"`
  - `[project.scripts]` → `mac-mcp = "mac_mcp:main"`
  - `[tool.hatch.build.targets.wheel]` → `packages = ["mac_mcp"]`
  - Add `license = "MIT"` (SPDX expression; hatchling-supported), `authors = [{name = "Andrei
    Lavrenov", email = "andrei@lav.ren"}]`, `keywords` (mcp, macos, apple, eventkit, calendar,
    reminders), `classifiers` (`Operating System :: MacOS`, `Environment :: MacOS X`,
    `Programming Language :: Python :: 3.11` / `3.12`, `Topic :: Utilities`). **No** `License ::`
    classifier — PEP 639 treats it as redundant with the SPDX `license` expression and newer build
    tools warn on the pair; the SPDX string is the single source of truth.
  - `[project.urls]`: Homepage, Repository, Issues, Changelog → the `mac-mcp` repo.
- Add `LICENSE` (MIT full text, © 2026 Andrei Lavrenov).
- `uv sync` to regenerate `uv.lock` under the new project name.

### Phase 3 — Release automation
- New `.github/workflows/release.yml`:
  - Trigger: `on: push: tags: ['v*']`.
  - Permissions: `id-token: write` (OIDC), `contents: write` (create release).
  - Runs on `ubuntu-latest` (wheel is pure Python — PyObjC is a runtime dep, not built here).
  - Steps: checkout → `astral-sh/setup-uv` → `uv build` → publish to PyPI via OIDC Trusted
    Publishing (`pypa/gh-action-pypi-publish` or `uv publish` with no token) → `gh release create`
    with the matching CHANGELOG section as the release body.
- One-time manual prerequisite (documented in the plan, not automatable from the repo): on PyPI,
  register a **pending Trusted Publisher** for project `mac-mcp` — owner `elfensky`, repo `mac-mcp`,
  workflow `release.yml`. Until this exists the first publish step will fail.
- `ci.yml` is unchanged (still macOS, still lint-gated) other than any `apple_mcp` string in it.

### Phase 4 — GitHub repo rename + external refs
- Rename the repo `elfensky/apple-mcp` → `elfensky/mac-mcp` (GitHub Settings or `gh repo rename`).
- Update local `git remote set-url origin` to the new URL.
- Update the `CLAUDE.md` tracker reference (`elfensky/apple-mcp` → `elfensky/mac-mcp`). The
  life-cockpit vault tracker entry is updated **out-of-repo** by the user; note it, don't edit here.

### Phase 5 — Cut the release
- Bump version `0.1.2` → `0.2.0` in `pyproject.toml`.
- Add a `CHANGELOG.md` `## [0.2.0]` entry documenting the rename (PyPI name, repo, binary, env var)
  and the first public PyPI publication.
- Commit, `git tag v0.2.0`, push tag, watch `release.yml`, confirm `mac-mcp` appears on PyPI and the
  GitHub Release is created. Smoke-test `uvx mac-mcp` (or `uvx --from . mac-mcp`).

## Verification gate

Run before claiming done (per `CLAUDE.md`, plus packaging checks):

```sh
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build            # produces dist/mac_mcp-0.2.0-*.whl + .tar.gz
```

A green `uv build` whose artifacts are named `mac_mcp-0.2.0-*` confirms the packaging rename landed.
Grep for stragglers: no `apple_mcp` / `APPLE_MCP` remains except the deliberate prior-art references
in `CREDITS.md`/`CHANGELOG.md` history.

## Out of scope (follow-ups)

- **Official MCP registry** (`server.json` + registry publish) — optional discoverability, do once
  `mac-mcp` is live on PyPI.
- Life-cockpit vault tracker update — handled by the user in the vault, not this repo.
