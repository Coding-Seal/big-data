# Extending with new sources

Beyond pageviews + page/categorylinks/linktarget + mediawiki_history
(already prototyped in `poc/`), these plug into the same
[layered design](layered-design.md) as new dimension/fact tables.
Location, format, and size for each live in `docs/sources/` — this table
only covers what each one adds architecturally and how it joins:

| Source | What it adds | Join key |
|---|---|---|
| [Wikidata](../sources/wikidata.md) | Real topic taxonomy — fixes the finding that raw `categorylinks` is dominated by maintenance categories, not topics. The strongest single upgrade for Q1/Q5. | `page_title` ↔ Wikidata sitelink |
| [Clickstream](../sources/clickstream.md) | Referrer flows: a spike sourced from external/search referrers looks structurally different from one sourced by internal wikilinks — useful for Q2. | `curr` (target article) ↔ `page_title` |
| [Redirect table](../sources/redirect.md) | Data-quality fix, not a new question: pageviews sometimes land on a redirect title rather than the canonical article, undercounting the real target unless consolidated. | `rd_from` = `page_id` |
| [Pagelinks](../sources/pagelinks.md) | In-degree (how many articles link to this one) — a second, independent "importance" signal for Q4 alongside length/revisions. | `page_id` |
| [Wikinews / ITN history](../sources/wikinews-itn.md) | An actual timeline of Wikipedia-recognized news events, without leaving the Wikimedia ecosystem — cheaper than an external news API for Q2. | date-matched against spike timestamps |
| [ORES](../sources/ores.md) | Independent article-quality signal beyond raw length, for Q4. Fetched via API rather than bulk dump — lower priority/slower to add. | `page_id` / `revision_id` |
| [Featured/Good Article status](../sources/featured-good-article.md) | Clean, binary "is this a maintained, high-quality article" flag — lets Q3/Q4 check whether recognized-quality articles decay differently after a traffic peak. | `page_id` |

None of these require touching the pageviews ingestion or existing question
code if [`layered-design.md`](layered-design.md) is followed — each is a
new **source module** producing a new **silver table**.
