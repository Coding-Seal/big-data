# Page dump (page + categorylinks + linktarget)

**Status:** in use (`src/sources/page_dump.py`, `src/common/sqldump.py`;
originally prototyped in `poc/ingest_dims.py`, `poc/sqldump.py`).

Three separate files, documented together because they're fetched from the
same place, share a format, and are only useful joined to each other — this
is the `sources/page_dump.py` module's input.

## Location

`https://dumps.wikimedia.org/<wiki>/latest/`:

- `<wiki>-latest-page.sql.gz`
- `<wiki>-latest-categorylinks.sql.gz`
- `<wiki>-latest-linktarget.sql.gz`

One-time **current-state snapshots**, not a time series — size doesn't
scale with the study date range. Same schema for every wiki; the PoC used
`simplewiki` (Simple English Wikipedia) instead of `enwiki` specifically to
keep iteration fast (~30MB dumps vs. multi-GB) — the same code works
unchanged on `enwiki` by changing the wiki name.

A sibling file, `redirect.sql.gz`, is documented separately in
[`redirect.md`](redirect.md) (not yet fetched).

## Format

Raw MySQL `INSERT` dump text — **not delimited data**. Needs a custom
parser; `src/common/sqldump.py` is a small hand-written one (handles quoted
strings, backslash escaping, and parenthesized tuples — not a general SQL
parser, just enough for what these dumps contain), run via Spark
(`textFile` + `mapPartitions`).

**Format surprise, confirmed against a real current file, not assumed from
classic mysqldump knowledge:** these are *not* single-mega-line
extended-insert statements (`INSERT INTO ... VALUES (1,...),(2,...);` all
on one line). The real format puts `VALUES` on its own line, then **one
tuple per following line**:
```
INSERT INTO `page` VALUES
(1933,0,'Gaol',1,0,0.888618879434,'20260408184256','20240815235917',3291625,20,'wikitext',NULL),
(1934,0,'Prison',0,0,0.84323923329,'20260903082906','20260903083408',10811574,11773,'wikitext',NULL),
...
```
This matters for anyone writing a parser against these dumps: a naive
line-by-line `line.find("VALUES (")` check silently matches nothing on the
header line and skips every data line — zero rows parsed, **no error**,
which is far more dangerous than a crash. It also rules out the seemingly
obvious fix of reading a whole file into one string to reassemble
statements (`SparkContext.wholeTextFiles`) — that overflowed the driver
JVM's heap on this ~30MB `simplewiki` dump alone. The working approach
streams line-by-line, tracking "am I inside this table's INSERT block"
across lines (see `src/sources/page_dump.py::_parse_table`).

**Schema, confirmed by reading each dump's own `CREATE TABLE` DDL directly**
(not assumed from memory or stale docs):

- `page`: `page_id, page_namespace, page_title, page_is_redirect,
  page_is_new, page_random, page_touched, page_links_updated, page_latest,
  page_len, page_content_model, page_lang`. `page_len` = current article
  byte length.
- `categorylinks`: **does not store category names directly** — a real
  MediaWiki schema migration normalized link tables to remove duplicated
  title strings. Columns of interest: `cl_from`, `cl_type`,
  `cl_target_id` — the last is a foreign key into `linktarget`.
- `linktarget`: `lt_id`, `lt_namespace`, `lt_title`.

**The real join chain is three dumps, not two:**
`page (page_id) → categorylinks (cl_from, cl_target_id) → linktarget (lt_id, lt_namespace, lt_title)`.
Filter `cl_type = 'page'` (excludes subcat/file links) and
`lt_namespace = 14` (Category namespace) to get clean page→category edges.

`enwiki-latest-revision.sql.gz` **no longer exists** in the dump listing
(confirmed absent) — don't plan around it; see
[`mediawiki-history.md`](mediawiki-history.md) for revision data instead.

**License:** not independently verified by this project — Wikimedia dump
terms vary by content type; pageviews are confirmed CC0 (see
[`pageviews.md`](pageviews.md)), this hasn't been separately checked.

## Example

Pulled directly from the current `simplewiki` dumps while writing this doc
— real rows, not constructed. `page_id` 950 is a real article (title
literally `"0"`) that happens to carry one category link, which makes it a
good illustration of the full three-table join chain end to end:

```sql
-- page.sql.gz: page_id 950
(950,0,'0',0,0,0.535833978344,'20260911192410','20260911192410',10993282,19498,'wikitext',NULL)

-- categorylinks.sql.gz: cl_from=950 -> cl_target_id=241619
(950,'','2025-09-27 09:01:06','','page',1,241619)

-- linktarget.sql.gz: lt_id=241619
(241619,14,'All_pages_needing_cleanup')
```

Joined: page **"0"** (`page_id=950`) belongs to category
**`All_pages_needing_cleanup`** (`lt_namespace=14` confirms it's a real
Category-namespace target) — a maintenance category, not a topic, which is
exactly the finding below in miniature. For contrast, `Main_Page` itself
(`page_id=232335`) carries no category links at all — pulled from the same
dump:

```sql
(232335,0,'Main_Page',0,0,0.625613103384,'20261001133408','20260922204010',10710583,3045,'wikitext',NULL)
```

## Size

Measured directly:

| File | enwiki | simplewiki (used in PoC) |
|---|---|---|
| `page.sql.gz` | 2.39GB | 32.7MB |
| `categorylinks.sql.gz` | 2.54GB | 28.5MB |
| `linktarget.sql.gz` | not measured | 37.8MB |

## Description

Fills the category gap pageviews can't answer alone (needed for Q1, Q3,
Q5) and provides current article length (`page_len`, needed for Q4).

**Known limitation, measured in the PoC, not theoretical:** raw
`categorylinks` is **dominated by maintenance/tracking categories, not
topics** — the top categories by views in a real 3-hour PoC run were things
like `Webarchive_template_wayback_links`, `Articles_with_hCards`,
`CS1_maint:_deprecated_archival_service`. Don't treat `category_dim` built
from this source as a topic taxonomy as-is; either filter maintenance
categories by name pattern (brittle) or bring in a real taxonomy — see
[`wikidata.md`](wikidata.md).

**Join quality, measured in the PoC:** joining the 3-hour `simple`
pageviews slice against `page_dim` matched **88.8%** of pageview rows to a
`page_id`. The rest are presumably very recent pages, redirects, or titles
that changed between the pageview window and the dump snapshot — expected,
not a bug.
