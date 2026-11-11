# Redirect table

**Status:** in use (`src/sources/page_dump.py` → `redirect_dim`, consumed through `src/questions/pages.py`). A data-quality fix, not a new question.

## Location

`https://dumps.wikimedia.org/<wiki>/latest/<wiki>-latest-redirect.sql.gz`, `page.sql.gz`'s sibling in the same directory (see [`page-dump.md`](page-dump.md)). Confirmed present for `simplewiki`.

## Format

Same raw MySQL `INSERT` dump format as `page.sql.gz` (`sqldump.py` applies unchanged). Confirmed schema, from the dump's own `CREATE TABLE`:

```sql
CREATE TABLE `redirect` (
  `rd_from` int(8) unsigned NOT NULL DEFAULT 0,
  `rd_namespace` int(11) NOT NULL DEFAULT 0,
  `rd_title` varbinary(255) NOT NULL DEFAULT '',
  `rd_interwiki` varbinary(32) DEFAULT NULL,
  `rd_fragment` varbinary(255) DEFAULT NULL,
  PRIMARY KEY (`rd_from`)
)
```

Notable finding, not assumed: unlike `categorylinks` (see [`page-dump.md`](page-dump.md)), this table was not migrated to the `linktarget`-style normalization. `rd_title` is still stored directly, no join needed. Join key: `rd_from` = `page_id`.

## Size

Measured: `simplewiki-latest-redirect.sql.gz` = 1.47MB, much smaller than `page.sql.gz`/`categorylinks.sql.gz` since most pages aren't redirects. enwiki not measured, but expect the same small-relative-to-page-dump proportion.

## Example

Real rows from the downloaded file:

```sql
(24,0,'Catharism','','')
(41,0,'United_States_customary_units','','')
(46,0,'AS','','')
```

`page_id=46` redirects to `AS` directly usable as a title string, no `linktarget` lookup required, unlike the category join in `page-dump.md`.

## Description

Which titles are redirects and what they point to. Pageviews sometimes land on a redirect title rather than the canonical article; without this table, those views are dropped by the `pageviews_fact` ↔ `page_dim` join (`page_dim` is namespace-0 non-redirect only), undercounting the real target article.

Measured, not estimated: on the 2026-10-04 10:00–11:00 `simplewiki` slice, 806 of 9,890 viewed titles, 1,026 views, 7.2% of all traffic, failed that join. The loss is not uniform: it lands on redirect titles for exactly the high-traffic, news-driven pages the questions care about (`Solar_system`, `Nobel_prize`, `Uranus_(planet)`, `Israel–Hamas_war`), plus first-letter case variants (`main_page`, `Main_page`) and pages created after the dump snapshot.

## How it's wired in

`page_dump.to_silver()` emits `redirect_dim(wiki, from_title, to_page_id, to_title)`: `redirect` joined to the redirect pages in `page.sql.gz` for the source title, then joined to `page_dim` for the target `page_id`. Question modules never touch it directly; they call `questions/pages.py::with_page_id()`, which unions canonical titles with redirect titles and also applies MediaWiki's first-letter capitalization rule ($wgCapitalLinks) to the requested title.

Two deliberate limits:

- Double redirects drop out. The target-side join is against `page_dim` (non-redirects), so a redirect pointing at another redirect finds nothing. That matches what a reader gets: MediaWiki doesn't follow the second hop either.
- Only namespace 0, matching `pageviews_fact`'s own filter.
