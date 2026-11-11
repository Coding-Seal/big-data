# mediawiki_history

**Status:** in use (`src/sources/mediawiki_history.py`); feeds `revision_dim` (Q4's revision-count half) and `itn_edit_fact` (Q2's news-timeline half, see [`wikinews-itn.md`](wikinews-itn.md)).

No "latest" alias exists for this dataset the way `page_dump.md`'s `{wiki_db}-latest-*` does, and only the last two monthly snapshot generations are retained. `download()` discovers the current snapshot and the real per-wiki filenames from the dumps site's own directory listings at run time rather than hardcoding a date, which would otherwise 404 within a couple of months. Confirmed directly: the snapshot this doc was originally written against (`2026-07`) had already rolled to `2026-08`/`2026-09` by the time the source module shipped.

## Location

`https://dumps.wikimedia.org/other/mediawiki_history/<snapshot>/<wiki>/<filename>.tsv.bz2`, e.g. `2026-08/enwiki/2026-08.enwiki.2024-01.tsv.bz2` for enwiki, or `2026-09/simplewiki/2026-09.simplewiki.all-time.tsv.bz2` for simplewiki, confirmed by listing the live `simplewiki/` directory, which contains exactly that one file, not a per-month series. Bigger wikis get one file per month (`<snapshot>.<wiki>.<YYYY-MM>.tsv.bz2`, capped at ~2GB each); smaller wikis get a single `<snapshot>.<wiki>.all-time.tsv.bz2` covering their whole history. `download()` lists the per-wiki directory rather than assuming which layout applies.

Only the last two monthly snapshot generations are retained on the dumps site (confirmed again while building the source module: the generations had already rolled from `2026-07`/`2026-08` to `2026-08`/`2026-09`), but each snapshot contains the wiki's entire history to date, not just that month, so this isn't a data-loss risk, just a retention detail. For wikis with monthly files, only the months the configured date range touches are downloaded, so there's no wasted bandwidth, unlike pageviews.

### It lags the pageviews dumps by weeks

A snapshot is a batch job, published well after the month it is named for, and its newest monthly file is a partial stub. Measured in the `2026-09` snapshot's `enwiki` directory:

| File | Generated | Size |
|---|---|---|
| `2026-09.enwiki.2026-08.tsv.bz2` | 05-Oct-2026 | 570MB |
| `2026-09.enwiki.2026-09.tsv.bz2` | 05-Oct-2026 | 557MB |
| `2026-09.enwiki.2026-10.tsv.bz2` | 05-Oct-2026 | **1.4MB** |

Pageviews, by contrast, are published hourly and are current to yesterday. So a date range inside the last few weeks gets full pageview coverage and nearly empty edit coverage. Two consequences, both of which would otherwise look like findings rather than gaps:

- Q2 can't tell "this spike wasn't near a news edit" from "no edit data exists for this hour" unless it checks. It does: `q2_spikes_news.py` reports three states, not a boolean.
- `revision_dim` covers only pages edited during the downloaded months. For a small wiki that's moot (one all-time file; simplewiki yields 605K pages, full coverage). For enwiki it is not: a one-month download means Q4's `avg_revisions` describes recently-edited pages, not the wiki. Widening it costs ~570MB per extra month and still never reaches "all pages"; the full enwiki history is ~10GB per recent year.

## Format

TSV + bzip2, splittable, unlike the pageviews gzip files. This is the one dataset in this pipeline actually built for Hadoop/Spark-scale consumption. Revision-level denormalized event log, with WMF-precomputed per-page edit counts and revision byte-size diffs, both metrics Q4 needs, in one dataset.

Schema now verified (this was previously this project's single biggest unverified detail, resolved while writing this doc by downloading the full `2026-08.enwiki.2001-01.tsv.bz2` file, 89KB, and cross-checking its 78 tab-separated fields per row against the column list on [wikitech's technical documentation page](https://wikitech.wikimedia.org/wiki/Analytics/Data_Lake/Edits/Mediawiki_history_dumps): counts and value types matched exactly). No header row is present in the file itself; column order is positional only, so the full ordered list matters:

- 1–6 **event fields**: `wiki_db, event_log_id, event_entity, event_type, event_timestamp, event_comment`
- 7–28 **event_user fields** (one row per edit, the acting user's state at that time): `event_user_id, event_user_central_id, event_user_text_historical, event_user_text, event_user_blocks_historical, event_user_blocks, event_user_groups_historical, event_user_groups, event_user_is_bot_by_historical, event_user_is_bot_by, event_user_is_created_by_self, event_user_is_created_by_system, event_user_is_created_by_peer, event_user_is_anonymous, event_user_is_temporary, event_user_is_permanent, event_user_is_cross_wiki, event_user_registration_timestamp, event_user_creation_timestamp, event_user_first_edit_timestamp, event_user_revision_count, event_user_seconds_since_previous_revision`
- 29–41 **page fields**: `page_id, page_title_historical, page_title, page_namespace_historical, page_namespace_is_content_historical, page_namespace, page_namespace_is_content, page_is_redirect, page_is_deleted, page_creation_timestamp, page_first_edit_timestamp, page_revision_count, page_seconds_since_previous_revision`
- 42–60 **user fields** (only populated when `event_entity = user`, empty on revision rows): `user_id, user_central_id, user_text_historical, user_text, user_blocks_historical, user_blocks, user_groups_historical, user_groups, user_is_bot_by_historical, user_is_bot_by, user_is_created_by_self, user_is_created_by_system, user_is_created_by_peer, user_is_anonymous, user_is_temporary, user_is_permanent, user_registration_timestamp, user_creation_timestamp, user_first_edit_timestamp`
- 61–78 **revision fields** (only populated when `event_entity = revision`): `revision_id, revision_parent_id, revision_minor_edit, revision_deleted_parts, revision_deleted_parts_are_suppressed, revision_text_bytes, revision_text_bytes_diff, revision_text_sha1, revision_content_model, revision_content_format, revision_is_deleted_by_page_deletion, revision_deleted_by_page_deletion_timestamp, revision_is_identity_reverted, revision_first_identity_reverting_revision_id, revision_seconds_to_identity_revert, revision_is_identity_revert, revision_is_from_before_page_creation, revision_tags`

For Q4, the fields that matter are `page_id`, `page_revision_count` (cumulative, already precomputed, no need to count rows per page) and `revision_text_bytes`/`revision_text_bytes_diff` (current size and size-change, for the "article length" half).

`revision.sql.gz` (the raw MediaWiki revision table) is checked and no longer published for enwiki, confirming `mediawiki_history` is the only practical source for revision counts at this scale, not the raw revision table.

## Size

Measured directly (enwiki, inside the `2026-08` snapshot):

| Metric | Value |
|---|---|
| Smallest monthly file (2001-01) | 89KB |
| Largest recent monthly file (2024-02) | 918MB |
| Typical recent month | ~800–920MB compressed |
| Full year of recent enwiki history | ~10GB compressed |

## Example

A real row from the downloaded `2026-08.enwiki.2001-01.tsv.bz2`: the `revision`-type event for enwiki's very first recorded edit (field numbers per the list above; empty fields omitted for readability):

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

(The `user_*` field block, 42–60, is entirely empty on this row since `event_entity = revision`, not `user`, confirmed directly, not assumed.)

## Description

Gives per-page edit counts and byte-size history: the half of Q4 (length × revision-count correlation vs. pageview volume) that `page-dump.md`'s snapshot `page_len` can't cover on its own, since that's current-state only with no history. Bronze→silver plan: read TSV (bzip2 splits normally), filter to actual edit events, aggregate to one row per page: revision count, first/last edit timestamp, running byte size, feeding the `revision_dim` silver table in `docs/arch/layered-design.md`.
