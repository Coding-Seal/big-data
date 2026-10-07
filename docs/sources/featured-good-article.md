# Featured / Good Article status

**Status:** not fetched — cheap, high-signal optional addition.

## Location

Either a Wikidata badge claim (see [`wikidata.md`](wikidata.md)) or a
specific MediaWiki category (e.g. `Category:Featured articles`,
`Category:Good articles`), reachable through the same
`categorylinks`/`linktarget` join chain documented in
[`page-dump.md`](page-dump.md). Whichever is chosen, this source piggybacks
on infrastructure another source already needs — it isn't a new ingestion
path by itself.

## Format

Inherits whichever of the two location options is used: Wikidata claim
format, or a `category_dim` row.

## Size

Not applicable on its own — negligible marginal cost on top of Wikidata or
`page-dump.md`.

## Example

Not independently fetched (enwiki's real `Category:Good_articles` wasn't
pulled this session — only `simplewiki`, which doesn't curate this the
same way enwiki does). Illustrative only, following the exact mechanism
already verified for real in [`page-dump.md`](page-dump.md):

```sql
-- categorylinks.sql.gz: some page is linked to the GA category
(<page_id>,'','<timestamp>','','page',1,<lt_id>)

-- linktarget.sql.gz: that lt_id resolves to the category
(<lt_id>,14,'Good_articles')
```

Same join chain, same two tables, as the maintenance-category example in
`page-dump.md` — the only difference is which category name you're
filtering for. That's exactly why this is cheap to add: no new source
module, just a different filter on a table already being parsed.

## Description

A clean, binary "is this a maintained, high-quality article" flag, keyed
on `page_id`. Lets Q3/Q4 check whether recognized-quality articles decay
differently after a traffic peak than random articles, or whether
Featured/Good status correlates with pageview volume independent of raw
length — a cheap enrichment once either Wikidata or the category join is
already in place for another reason.
