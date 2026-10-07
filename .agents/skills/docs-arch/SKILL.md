---
name: docs-arch
description: Use when creating or updating architecture documentation under docs/arch (system design, the source/question module contracts, the silver table schema) — keeps the design docs authoritative and in sync with the code.
---

# Working with docs/arch

`docs/arch/` holds the durable design documentation for the pipeline, one
file per concern — see `docs/arch/README.md` for the current index
(layered design, extending with new sources, PoC mapping, implementation
order, ingestion/storage). It is meant to stay a small number of living
documents, not an append-only log of every design conversation.

## Before changing a doc in this directory

- If the change is implementing something a doc already describes, you
  generally don't need to edit the doc — just keep the code matching it.
- If the change *diverges* from what's documented (new silver table, new
  method on the source/question interface, a rejected pattern becoming
  adopted after all), update `layered-design.md` in the same change — it
  describes the contract, and a stale contract is worse than no contract.
- If you're adding a new data source, check `docs/sources/` first for
  whether it's already been scoped (join key, format, size), then add it to
  `extending-with-new-sources.md` rather than inventing new integration
  notes from scratch.

## Conventions for this directory

- **Extend the contract, don't mutate it, when documenting a new source.**
  E.g. a new `topic_dim` from Wikidata is a new entry in the silver schema
  list alongside `category_dim`, not a rewrite of `category_dim`'s row —
  this mirrors the actual engineering rule (see `AGENTS.md`).
- **Keep "Deliberately not doing" (in `layered-design.md`) honest.** If a
  rejected approach (a scheduler, a table format library, plugin
  auto-discovery) is later adopted, update or remove that line instead of
  leaving it stale — a reader should be able to trust that list as current,
  not historical.
- **One file per concern, not one file per conversation.** This directory
  used to be a single growing `architecture.md`; it was split into the
  current per-concern files specifically to stop that growth. For a new
  design decision that doesn't fit an existing file, add a new
  `docs/arch/<topic>.md`, link it from `docs/arch/README.md`'s index, and
  cross-link it from whichever existing file it relates to — don't grow an
  existing file past the one concern its name promises, and don't write a
  throwaway handoff note instead. (A dense "feed this to the next session"
  recap is fine as scratch context *within* a conversation, but shouldn't
  be committed as a permanent doc — fold anything genuinely new it contains
  into the real docs and discard the rest.)
- **`poc-mapping.md` is temporary scaffolding**, not a permanent design
  doc. Once the migration it describes actually happens and `poc/` is
  retired, delete it rather than maintaining it against code it no longer
  matches.
