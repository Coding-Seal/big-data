# ORES / article quality scores

**Status:** not fetched — optional enrichment, lower priority than the
other sources here.

## Location

`https://ores.wikimedia.org/` API. Not a bulk dump — fetched per-request
(per `page_id`/`revision_id`), which makes it slower and more operationally
different to integrate than every other source in this directory.

## Format

JSON API responses.

## Size

Not applicable — this is a live API, not a downloadable file; "size" would
be request volume (one call per article/revision scored), not bytes on
disk.

## Example

`ores.wikimedia.org` is outside the domains this project has fetched from
so far (everything else lives on `dumps.wikimedia.org`), so this is the
API's publicly documented response shape, not a result this project
independently verified — flagged as such rather than presented as
measured, per this project's own rule:

```json
{
  "enwiki": {
    "scores": {
      "12345": {
        "articlequality": {
          "score": {
            "prediction": "GA",
            "probability": {"FA": 0.01, "GA": 0.85, "B": 0.1, "C": 0.02, "Start": 0.01, "Stub": 0.01}
          }
        }
      }
    }
  }
}
```

`"12345"` is a `revision_id` — this is the actual integration cost: one
HTTP round-trip per revision scored, vs. one bulk file read for every other
source here.

## Description

An independent article-quality signal beyond raw length, for Q4. Because
it's fetched via API rather than bulk dump, it doesn't fit the
bronze→silver batch pattern the other sources use as cleanly — integrating
it would mean either a slow one-time enrichment pass cached to a silver
table, or deciding it's not worth the operational cost relative to length
+ revision-count (which already come from bulk dumps). Not scoped further
than this until/unless it's actually prioritized.
