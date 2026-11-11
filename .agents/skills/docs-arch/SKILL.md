---
name: docs-arch
description: Use when creating or updating architecture documentation under docs/arch (system design, the source/question module contracts, the silver table schema) — keeps the design docs authoritative and in sync with the code.
---

# Working with docs/arch

`docs/arch/` holds the durable design documentation for the pipeline, one file per concern — see `docs/arch/README.md` for the current index (layered design, ingestion/storage). It is meant to stay a small number of living documents, not an append-only log of every design conversation or build history — that goes to git and `tasks.md` instead.

## Before changing a doc in this directory

- If the change is implementing something a doc already describes, you generally don't need to edit the doc — just keep the code matching it.
- If the change *diverges* from what's documented (new silver table, new method on the source/question interface, a rejected pattern becoming adopted after all), update `layered-design.md` in the same change — it describes the contract, and a stale contract is worse than no contract.
- If you're adding a new data source, check `docs/sources/` first for whether it's already been scoped (join key, format, size) before writing new integration notes from scratch. If it isn't, add a new `docs/sources/<name>.md` and list it in `docs/sources/README.md`'s table.

## Conventions for this directory

- **Extend the contract, don't mutate it, when documenting a new source.** E.g. a new `topic_dim` from Wikidata is a new entry in the silver schema list alongside `category_dim`, not a rewrite of `category_dim`'s row — this mirrors the actual engineering rule (see `AGENTS.md`).
- **Keep "Deliberately not doing" (in `layered-design.md`) honest.** If a rejected approach (a scheduler, a table format library, plugin auto-discovery) is later adopted, update or remove that line instead of leaving it stale — a reader should be able to trust that list as current, not historical.
- **One file per concern, not one file per conversation.** This directory used to be a single growing `architecture.md`, split into per-concern files specifically to stop that growth. A new design decision that doesn't fit an existing file gets a new `docs/arch/<topic>.md`, linked from `docs/arch/README.md`'s index and cross-linked from whichever file it relates to — don't grow an existing file past its one concern, and don't commit a "feed this to the next session" handoff note as a permanent doc; fold anything genuinely new into the real docs instead.
- **Delete a doc once what it describes is resolved**, built or dropped — a "planned" source doc for something that never got built, or a build-order doc for a build that already finished, is dead weight once the thing it was tracking resolves one way or the other. The resolution belongs in `tasks.md` or git history, not a doc that still reads like an open question.
