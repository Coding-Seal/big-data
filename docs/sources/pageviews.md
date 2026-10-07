# Pageviews

**Status:** in use (prototyped in `poc/ingest.py`).

## Location

`https://dumps.wikimedia.org/other/pageviews/<YYYY>/<YYYY>-<MM>/` — one
file per UTC hour: `pageviews-YYYYMMDD-HH0000.gz`. The timestamp marks the
*end* of the aggregation window. Covers **May 2015 to present**, updated
continuously. (An older `pagecounts-raw` format covers 2007–2015 but is
deprecated by Wikimedia and not used here. A coarser monthly/per-article
companion dataset, `pageview_complete`, also exists but isn't used — this
project needs hourly/daily resolution.)

## Format

Plain text, gzip-compressed, space-separated, 4 fields, **no header**:

```
domain_code  page_title  count_views  total_response_size
```

**Real example row**, pulled directly from
`pageviews-20261004-100000.gz` (2026-10-04, 10:00–11:00 UTC) while writing
this doc:

```
en Main_Page 191214 0
```

(`total_response_size` is 0 in current files — confirms the "effectively
vestigial" note below; it isn't always populated.)

| Field | Meaning |
|---|---|
| `domain_code` | Project + language, e.g. `en` (English Wikipedia desktop), `en.m` (mobile), `en.d` (Wiktionary), `commons.m`, `en.wikidata`. Full code list is a separate lookup file linked from the readme. |
| `page_title` | URL-decoded title, underscores for spaces. **Includes all namespaces** — Talk:, Category:, Special:, User: pages are mixed in with articles; nothing in the row itself flags which is which. Must be filtered by title-prefix to get articles only (see `poc/ingest.py::NAMESPACE_PREFIXES` — an approximation, not a formal namespace lookup). |
| `count_views` | The metric of interest. |
| `total_response_size` | Bytes served — effectively vestigial in modern files, not relied on. |

Lines are pre-sorted by `domain_code`, then `page_title`.

**Compression gotcha:** gzip is **not splittable** — each file is one
indivisible unit of work for a Spark task regardless of size. Parallelism
comes from file count (24/day), not intra-file splits.

**Bot filtering:** applied server-side "as best they can," acknowledged by
Wikimedia as imperfect (e.g. a known historical spike from misidentified
Chrome 41 requests). No per-line agent-type flag is exposed — you get one
already-filtered count, not raw vs. filtered variants.

**License:** CC0.

## Size

Measured directly (not estimated from generic knowledge — these datasets
change and public figures go stale):

| Metric | Value |
|---|---|
| Single hourly `.gz`, all projects | 44–84 MB (avg ~60MB) |
| All-projects, 1 month | ~40GB |
| All-projects, 1 year | ~500GB compressed |
| en.wikipedia share of total daily *views* (Jan 2024, pageviews REST API) | ~40–44% (395M / 910M views/day) |

**View-share overestimates row/byte-share** — measured directly in the PoC
(3 hours, `en`+`en.m`, main namespace only): **28.4% of rows / 42.3% of
bytes**, vs. the 40–44% view-share figure. Row count is driven by how many
distinct articles get touched, not by how concentrated the views are. Use
30–45% as a range, not a point estimate, for capacity planning, and
re-measure at whatever scale is actually used.

## Description

Hourly aggregated pageview counts for every Wikimedia project (Wikipedia,
Wiktionary, Wikidata, Commons, etc.) in every language. This is the
project's core fact table — it's the only source that directly gives the
time series each of the five research questions is built around. On its
own it provides project, language, page title, and hourly view count, and
nothing else: no category, no content, no edit history, no news context.
Everything else in `docs/sources/` exists to fill one of those gaps.
