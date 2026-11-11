# Data sources

One file per Wikimedia dataset this project uses or could use. Each file covers that source's location, format, size, and description; see `.agents/skills/docs-arch/SKILL.md`'s sibling conventions for how these relate to `docs/arch/`. Numbers here are measured directly against the live dumps wherever marked as such, not recalled from general knowledge, since these datasets drift (schemas migrate, retention windows roll) and public knowledge about them goes stale.

| Source | Status | What it adds |
|---|---|---|
| [`pageviews.md`](pageviews.md) | **In use** | Core fact table: hourly views per article, every project/language |
| [`page-dump.md`](page-dump.md) | **In use** | Article namespace, length, and (noisy) categories |
| [`redirect.md`](redirect.md) | **In use** | Consolidates views landing on redirect titles |
| [`mediawiki-history.md`](mediawiki-history.md) | **In use** | Per-page revision count and byte-size history |
| [`wikinews-itn.md`](wikinews-itn.md) | **In use** (needs `enwiki`) | In-ecosystem news timeline (Q2's news correlation) |

Every file above includes a concrete example pulled from a real, currently live dump, verified while writing this index and not recalled from general knowledge. A real topic taxonomy (Wikidata, fixing `page-dump.md`'s maintenance-category problem) is still a known gap, see `tasks.md`'s `topic_dim` item, but isn't scoped as a doc here until it's actually worked on.

See `docs/arch/layered-design.md` for how each of these maps onto a `sources/*.py` module and a silver table, and `docs/arch/ingestion-storage.md` for the ingestion/storage strategy (bronze→silver→gold, streaming ingestion, local→cloud scaling).

## Combined sizing (all sources in use)

Scoped to English Wikipedia, one year, not the full multilingual, multi-year archive, since that scope alone runs to hundreds of GB and isn't necessary to answer any of the five research questions.

| Component | Size |
|---|---|
| Pageviews raw bronze (all projects, forced download) | ~500GB, but transient: filter-then-delete per file keeps peak local usage to a few hundred MB at a time |
| Pageviews silver (English-filtered Parquet, retained) | ~60–150GB (estimate, needs empirical calibration at full scale; see `pageviews.md`) |
| mediawiki_history raw (enwiki only) | ~10GB |
| mediawiki_history silver (per-page aggregate) | <1GB |
| `page.sql.gz` + `categorylinks.sql.gz` (one-time) | ~5GB raw |
| Gold chart specs (per-question, Vega-Lite JSON) | KBs–low MBs |
| **Total retained long-term** | **~70–160GB** |

Recommendations:
- Stream bronze ingestion (download one file → filter → delete → next) rather than staging the full ~500GB of raw pageviews at once; it's the single biggest lever on local disk pressure.
- Locally, a full year is workable with streaming ingest (plan for ~250GB free disk as headroom); a 1–2 month dev slice needs only ~10–20GB.
- On the university cloud, none of these numbers are large for object storage, so there's no need to be as careful about deleting raw files once off local disk.
- Calibrate before committing a budget: the 60–150GB pageviews-silver estimate is a starting point based on a 3-hour sample, not a verified figure at scale.
