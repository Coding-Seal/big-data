# mediawiki_history

**Status:** planned, not yet ingested into the pipeline — recommended
source for Q4's revision-count/length-history half (see
`docs/arch/implementation-order.md`, step 4). Schema is
now verified against a real downloaded file (below), which was the one
remaining blocker before writing `sources/mediawiki_history.py`.

## Location

`https://dumps.wikimedia.org/other/mediawiki_history/<snapshot>/<wiki>/<snapshot>.<wiki>.<YYYY-MM>.tsv.bz2`,
e.g. `2026-08/enwiki/2026-08.enwiki.2024-01.tsv.bz2`. One file per wiki per
month/year (bigger wikis get monthly files, smaller ones yearly or
single-file), capped at ~2GB.

Only the **last two monthly snapshot generations** are retained on the
dumps site (confirmed: currently `2026-07/` and `2026-08/` only) — but each
snapshot contains the wiki's **entire history to date**, not just that
month, so this isn't a data-loss risk, just a retention detail. Since
files are already per-wiki, only the `enwiki` files covering the target
date range need downloading — no wasted bandwidth, unlike pageviews.

## Format

TSV + bzip2 — **splittable**, unlike the pageviews gzip files. This is the
one dataset in this pipeline actually built for Hadoop/Spark-scale
consumption. Revision-level denormalized event log, with WMF-precomputed
per-page edit counts and revision byte-size diffs — both metrics Q4 needs,
in one dataset.

**Schema now verified** (this was previously this project's single biggest
unverified detail — resolved while writing this doc, by downloading the
full `2026-08.enwiki.2001-01.tsv.bz2` file, 89KB, and cross-checking its 78
tab-separated fields per row against the column list on
[wikitech's technical documentation page](https://wikitech.wikimedia.org/wiki/Analytics/Data_Lake/Edits/Mediawiki_history_dumps)
— counts and value types matched exactly). No header row is present in the
file itself; column order is positional only, so the full ordered list
matters:

1–6 **event fields**: `wiki_db, event_log_id, event_entity, event_type, event_timestamp, event_comment`
7–28 **event_user fields** (one row per edit — the acting user's state at that time): `event_user_id, event_user_central_id, event_user_text_historical, event_user_text, event_user_blocks_historical, event_user_blocks, event_user_groups_historical, event_user_groups, event_user_is_bot_by_historical, event_user_is_bot_by, event_user_is_created_by_self, event_user_is_created_by_system, event_user_is_created_by_peer, event_user_is_anonymous, event_user_is_temporary, event_user_is_permanent, event_user_is_cross_wiki, event_user_registration_timestamp, event_user_creation_timestamp, event_user_first_edit_timestamp, event_user_revision_count, event_user_seconds_since_previous_revision`
29–41 **page fields**: `page_id, page_title_historical, page_title, page_namespace_historical, page_namespace_is_content_historical, page_namespace, page_namespace_is_content, page_is_redirect, page_is_deleted, page_creation_timestamp, page_first_edit_timestamp, page_revision_count, page_seconds_since_previous_revision`
42–60 **user fields** (only populated when `event_entity = user`, empty on revision rows): `user_id, user_central_id, user_text_historical, user_text, user_blocks_historical, user_blocks, user_groups_historical, user_groups, user_is_bot_by_historical, user_is_bot_by, user_is_created_by_self, user_is_created_by_system, user_is_created_by_peer, user_is_anonymous, user_is_temporary, user_is_permanent, user_registration_timestamp, user_creation_timestamp, user_first_edit_timestamp`
61–78 **revision fields** (only populated when `event_entity = revision`): `revision_id, revision_parent_id, revision_minor_edit, revision_deleted_parts, revision_deleted_parts_are_suppressed, revision_text_bytes, revision_text_bytes_diff, revision_text_sha1, revision_content_model, revision_content_format, revision_is_deleted_by_page_deletion, revision_deleted_by_page_deletion_timestamp, revision_is_identity_reverted, revision_first_identity_reverting_revision_id, revision_seconds_to_identity_revert, revision_is_identity_revert, revision_is_from_before_page_creation, revision_tags`

For Q4, the fields that matter are `page_id`, `page_revision_count`
(cumulative, already precomputed — no need to count rows per page) and
`revision_text_bytes`/`revision_text_bytes_diff` (current size and
size-change, for the "article length" half).

**`revision.sql.gz`** (the raw MediaWiki revision table) is checked and
**no longer published** for enwiki — confirming `mediawiki_history` is the
only practical source for revision counts at this scale, not the raw
revision table.

## Size

Measured directly (enwiki, inside the `2026-08` snapshot):

| Metric | Value |
|---|---|
| Smallest monthly file (2001-01) | 89KB |
| Largest recent monthly file (2024-02) | 918MB |
| Typical recent month | ~800–920MB compressed |
| Full year of recent enwiki history | ~10GB compressed |

## Example

A real row from the downloaded `2026-08.enwiki.2001-01.tsv.bz2` — the
`revision`-type event for enwiki's very first recorded edit (field numbers
per the list above; empty fields omitted for readability):

```
event fields:   wiki_db=enwiki  event_entity=revision  event_type=create
                event_timestamp=2001-01-15 19:27:13.0  event_comment=*
event_user:     event_user_id=11313587  event_user_text=Office.bomis.com
                event_user_revision_count=1
page:           page_id=26323569  page_title=HomePage  page_namespace=0
                page_revision_count=1
revision:       revision_id=908493298  revision_parent_id=0
                revision_text_bytes=26  revision_text_bytes_diff=26
                revision_text_sha1=hjnc5wxv75ckwvos9wsd0as31nmnice
```

(The `user_*` field block, 42–60, is entirely empty on this row since
`event_entity = revision`, not `user` — confirmed directly, not assumed.)

## Description

Gives per-page edit counts and byte-size history — the half of Q4 (length
× revision-count correlation vs. pageview volume) that `page-dump.md`'s
snapshot `page_len` can't cover on its own, since that's current-state
only with no history. Bronze→silver plan: read TSV (bzip2 splits
normally), filter to actual edit events, aggregate to one row per page:
revision count, first/last edit timestamp, running byte size — feeding
the `revision_dim` silver table in `docs/arch/layered-design.md`.
