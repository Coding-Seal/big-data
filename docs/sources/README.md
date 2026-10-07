# Data sources

One file per Wikimedia dataset this project uses or could use. Each file
covers that source's location, format, size, and description — see
`.agents/skills/docs-arch/SKILL.md`'s sibling conventions for how these
relate to `docs/arch/`. Numbers here are **measured directly** against the
live dumps wherever marked as such, not recalled from general knowledge —
these datasets drift (schemas migrate, retention windows roll), and public
knowledge about them goes stale.

| Source | Status | What it adds |
|---|---|---|
| [`pageviews.md`](pageviews.md) | **In use** | Core fact table: hourly views per article, every project/language |
| [`page-dump.md`](page-dump.md) | **In use** | Article namespace, length, and (noisy) categories |
| [`mediawiki-history.md`](mediawiki-history.md) | Planned (Q4), schema verified | Per-page revision count and byte-size history |
| [`clickstream.md`](clickstream.md) | Scoped, sample verified | Referrer type per article (internal/search/external) |
| [`redirect.md`](redirect.md) | Schema verified, not wired in | Consolidates views landing on redirect titles |
| [`pagelinks.md`](pagelinks.md) | Schema verified, not wired in | In-degree per article, a second importance signal |
| [`wikidata.md`](wikidata.md) | Not fetched, location confirmed | Real topic taxonomy — fixes `page-dump.md`'s maintenance-category problem |
| [`wikinews-itn.md`](wikinews-itn.md) | Not fetched, location confirmed | In-ecosystem news timeline (Q2's missing source) |
| [`ores.md`](ores.md) | Not fetched, optional | Article quality score (API, not a bulk dump) |
| [`featured-good-article.md`](featured-good-article.md) | Not fetched, optional | Binary high-quality-article flag |

Every file above includes a concrete example pulled from a real, currently
live dump (except `ores.md` and `featured-good-article.md`, clearly marked
where the example is illustrative rather than independently fetched) —
verified while writing this index, not recalled from general knowledge.

See `docs/arch/layered-design.md` for how each of these maps onto a
`sources/*.py` module and a silver table, and `docs/arch/ingestion-storage.md`
for the ingestion/storage strategy (bronze→silver→gold, streaming
ingestion, local→cloud scaling).

## Combined sizing (sources currently in use or planned for Q4)

Scoped to **English Wikipedia, one year** — not the full multilingual,
multi-year archive, since that scope alone runs to hundreds of GB and
isn't necessary to answer any of the five research questions. This only
covers the three sources above with real numbers; the rest don't have
confirmed sizes yet (see each file).

| Component | Size |
|---|---|
| Pageviews raw bronze (all projects, forced download) | ~500GB — but **transient**: filter-then-delete per file keeps peak local usage to a few hundred MB at a time |
| Pageviews silver (English-filtered Parquet, retained) | ~60–150GB (estimate — needs empirical calibration at full scale; see `pageviews.md`) |
| mediawiki_history raw (enwiki only) | ~10GB |
| mediawiki_history silver (per-page aggregate) | <1GB |
| `page.sql.gz` + `categorylinks.sql.gz` (one-time) | ~5GB raw |
| Gold chart specs (per-question, Vega-Lite JSON) | KBs–low MBs |
| **Total retained long-term** | **~70–160GB** |

Recommendations:
- **Stream bronze ingestion** (download one file → filter → delete →
  next) rather than staging the full ~500GB of raw pageviews at once —
  the single biggest lever on local disk pressure.
- **Locally:** workable for a full year with streaming ingest (plan for
  ~250GB free disk as headroom); a 1–2 month dev slice needs only
  ~10–20GB.
- **On the university cloud:** none of these numbers are large for object
  storage — no need to be as careful about deleting raw files once off
  local disk.
- **Calibrate before committing a budget:** the 60–150GB pageviews-silver
  estimate is a starting point based on a 3-hour sample, not a verified
  figure at scale.
