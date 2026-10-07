# Redirect table

**Status:** schema and location verified (downloaded the full `simplewiki`
file while writing this doc); not yet wired into the pipeline — still a
data-quality fix, not a new question.

## Location

`https://dumps.wikimedia.org/<wiki>/latest/<wiki>-latest-redirect.sql.gz` —
`page.sql.gz`'s sibling in the same directory (see
[`page-dump.md`](page-dump.md)). Confirmed present for `simplewiki`.

## Format

Same raw MySQL `INSERT` dump format as `page.sql.gz` (`sqldump.py`
applies unchanged). Confirmed schema, from the dump's own `CREATE TABLE`:

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

**Notable finding, not assumed:** unlike `categorylinks` and `pagelinks`
(see [`page-dump.md`](page-dump.md), [`pagelinks.md`](pagelinks.md)),
this table was **not** migrated to the `linktarget`-style normalization —
`rd_title` is still stored directly, no join needed. Join key:
`rd_from` = `page_id`.

## Size

Measured: `simplewiki-latest-redirect.sql.gz` = 1.47MB — much smaller than
`page.sql.gz`/`categorylinks.sql.gz` since most pages aren't redirects.
enwiki not measured, but expect the same small-relative-to-page-dump
proportion.

## Example

Real rows from the downloaded file:

```sql
(24,0,'Catharism','','')
(41,0,'United_States_customary_units','','')
(46,0,'AS','','')
```

`page_id=46` redirects to `AS` directly usable as a title string — no
`linktarget` lookup required, unlike the category join in `page-dump.md`.

## Description

Which titles are redirects and what they point to. Pageviews sometimes
land on a redirect title rather than the canonical article — without this
table, those views are either dropped or incorrectly attributed, slightly
undercounting the real target article. This is a correctness fix for the
existing `pageviews_fact` ↔ `page_dim` join, not a new silver table or a
new research-question capability.
