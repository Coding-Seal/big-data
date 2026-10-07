# Pagelinks

**Status:** schema and location verified (downloaded the full `simplewiki`
file while writing this doc); not yet wired into the pipeline.

## Location

`https://dumps.wikimedia.org/<wiki>/latest/<wiki>-latest-pagelinks.sql.gz`.
Confirmed present for `simplewiki`.

## Format

Raw MySQL `INSERT` dump, same family as `page.sql.gz`. **Confirmed
migrated to a `linktarget`-style schema**, exactly the pattern found in
[`page-dump.md`](page-dump.md) for `categorylinks` — the old `pl_title`
column is in fact gone:

```sql
CREATE TABLE `pagelinks` (
  `pl_from` int(8) unsigned NOT NULL DEFAULT 0,
  `pl_from_namespace` int(11) NOT NULL DEFAULT 0,
  `pl_target_id` bigint(20) unsigned NOT NULL,
  PRIMARY KEY (`pl_from`,`pl_target_id`)
)
```

Join key: `pl_target_id` → `linktarget.lt_id` (same `linktarget` table
`page-dump.md` already joins through — no new dimension table needed, just
a new fact read off a table this project already parses).

## Size

Measured: `simplewiki-latest-pagelinks.sql.gz` = 84MB — notably larger
than `page.sql.gz`/`categorylinks.sql.gz` (~30MB each), since most articles
contain several outgoing links. enwiki not measured, but expect it to
scale up by the same multiple.

## Example

Real rows from the downloaded file — page 950 (the article titled `"0"`,
also used as the example in [`page-dump.md`](page-dump.md)) links to three
targets, resolved through the same `linktarget` table:

```sql
-- pagelinks.sql.gz: pl_from=950
(950,0,232)
(950,0,3556)
(950,0,5922)

-- linktarget.sql.gz: lt_id=232
(232,10,'Cite_book')
```

So page 950 links to `Template:Cite_book` (`lt_namespace=10` = Template) —
an ordinary citation-template transclusion, not an article-to-article
link; a real pipeline would need to filter `lt_namespace = 0` to count only
article-to-article in-degree for Q4.

## Description

In-degree per article (how many articles link to it) — a second,
independent "importance" signal for Q4, alongside article length and
revision count from [`mediawiki-history.md`](mediawiki-history.md). Would
extend `page_dim` or add a new silver column, not replace anything
existing.
