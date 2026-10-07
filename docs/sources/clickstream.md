# Clickstream

**Status:** not fetched into the pipeline, but scoped — existence, format,
size, and a real sample row have all been directly confirmed.

## Location

`https://dumps.wikimedia.org/other/clickstream/<YYYY-MM>/`, e.g.
`clickstream-enwiki-2026-09.tsv.gz` (the current latest month at the time
of writing — confirmed by listing the live directory, which currently goes
up to `2026-09/`). Monthly since 2017-11. Only published for ~11
major-language wikis (not every wiki has a clickstream file).

## Format

TSV, gzip-compressed, no header. Columns, confirmed by inspecting a real
file: `prev` (referrer), `curr` (target article), `type` (referrer type —
`other-empty`/`other-search`/`other-internal`/etc.), `n` (count). Join key
for this project: `curr` ↔ `page_title`.

## Size

Measured directly: `clickstream-enwiki-2026-09.tsv.gz` = 479MB (previously
measured at 453MB for the 2024-01 file — consistent order of magnitude
over time).

## Example

Real rows from the current `clickstream-enwiki-2026-09.tsv.gz`:

```
other-empty	Main_Page	external	179295498
other-search	Palace_of_Sporting_Games	external	12
other-internal	Main_Page	external	14407313
```

`Main_Page` getting both a huge `other-empty` (direct navigation/bookmark,
no referrer) and a large `other-internal` count in the same month
illustrates exactly the Q2 signal this source exists for: referrer-type
mix differs a lot by page and by traffic driver.

## Description

Referrer flows per article — did traffic arrive via internal wikilinks,
search engines, or external sites. Useful for Q2 (spikes vs. news): a
spike sourced from external/search referrers looks structurally different
from one sourced by internal wikilinks, which is a signal a news-driven
spike should show up as (people searching for the news topic and landing
directly) vs. an organic internal-traffic pattern. Would land as a new
`clickstream_fact(wiki, month, referrer, target_page, referrer_type, n)`
silver table per `docs/arch/layered-design.md`.
