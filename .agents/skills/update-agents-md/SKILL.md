---
name: update-agents-md
description: Use when adding or changing project-wide agent instructions in AGENTS.md (the shared instruction file for Claude Code, Codex, and opencode) — keeps it terse, non-duplicated, and in sync with CLAUDE.md.
---

# Editing AGENTS.md

`AGENTS.md` at the repo root is the single canonical instruction file for
every coding agent used on this project. `CLAUDE.md` is a one-line import
(`@AGENTS.md`) — Codex and opencode read `AGENTS.md` directly. There is
exactly one place to edit; never add a second instructions file.

## Before editing

1. Read the current `AGENTS.md` in full — it's short by design.
2. Check whether the content you want to add already lives in
   `docs/arch/*.md` or `docs/sources/*.md`. If so, link to it instead of
   restating it. `AGENTS.md` should stay a pointer + the handful of facts
   an agent needs *before* it has read the docs (environment setup, the
   silver-table seam rule, known gotchas) — not a second copy of those
   docs.

## Where new content goes

- A new non-obvious environment issue (like the Python 3.11 pin) →
  "Known gotchas worth not re-discovering".
- A new structural rule about how code must be organized → "Conventions".
- A new directory at the repo root → "Repo layout", one line.
- A new install/build/test command → "Environment".
- Anything that only matters to one specific agent (Claude Code, Codex,
  opencode) → a new `## <Tool> notes` section at the bottom of this same
  file, not a separate file. If you're tempted to write Claude-only content,
  ask whether it's really Claude-specific or just something that hasn't
  been generalized yet.

## Keep it terse

Each bullet should be one fact an agent would otherwise get wrong or
re-derive at cost — the "don't re-discover this" test. If a bullet needs
more than ~3 lines to explain, it belongs in `docs/arch/` or
`docs/sources/` with a link from here, not inline.

## After editing

- Re-read the whole file once more — it should still read as a short brief,
  not an accumulating log. Prune anything that's been superseded (e.g. a
  gotcha that's since been fixed for good, not just worked around).
- Don't touch `CLAUDE.md` — it should always remain exactly `@AGENTS.md`.
