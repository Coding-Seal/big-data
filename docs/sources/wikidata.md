# Wikidata

**Status:** not fetched into the pipeline — highest-value next addition for
Q1/Q5. Location and real format confirmed while writing this doc.

## Location

`https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.gz`
(also published as `.bz2`) — confirmed present by listing the live
directory. This is simpler than it might seem: it's on the same
`dumps.wikimedia.org` host as every other source here, not a separate
system. The live SPARQL endpoint (`query.wikidata.org`) is an alternative
not explored in this project.

## Format

Confirmed by downloading the first few KB: a single huge JSON array, one
object per entity, gzip-compressed, **no line-per-record structure** —
unlike every other source in this project, this isn't naturally
Spark-splittable without a JSON-aware reader (Spark's `multiline` JSON
mode, or pre-splitting). This is a real difference from the SQL-dump and
TSV sources and should be accounted for when scoping the ingestion
approach, not assumed to behave like `page-dump.md`'s files.

## Example

Real fragment, from the first ~1.5KB of the live file (truncated —
`labels` runs to hundreds of languages per entity):

```json
[
{"type":"item","id":"Q31","labels":{"el":{"language":"el","value":"Βέλγιο"},"es":{"language":"es","value":"Bélgica"}, ...}}
```

`Q31` is Belgium — confirmed by the real `"value":"Bélgica"` /
`"Βέλγιο"` labels. Each entity also carries `claims` (including `P31`
"instance of" — the taxonomy this project would actually use) and
`sitelinks` (including an `enwiki` entry with the page title — the join
key). This project didn't fetch far enough into a single entity's claims
to pull a real `P31` example without downloading a much larger range —
that's the next step if this source gets implemented.

## Size

Not measured — the file is large enough (the full dump covers every
Wikidata item, not just ones Wikipedia projects use) that this project
would almost certainly only want a filtered slice: sitelinks +
instance-of/subclass-of claims for pages already in `page_dim`, not the
full entity graph. Size that slice once the extraction approach is chosen.

## Description

Provides the `instance of` / `subclass of` hierarchy — a real topic
taxonomy, joined via `page_title` ↔ Wikidata sitelink. This directly fixes
the finding documented in [`page-dump.md`](page-dump.md): raw
`categorylinks` is dominated by maintenance/tracking categories, not
topics, so Q1 and Q5 ("traffic by topic") can't be answered well without
either this or a hand-curated category filter. Per
`docs/arch/layered-design.md`, adding this means a new `topic_dim` silver
table **alongside** `category_dim`, not a replacement — existing code
depending on `category_dim` keeps working.
