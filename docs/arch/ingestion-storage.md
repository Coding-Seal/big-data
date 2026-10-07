# Ingestion & storage strategy

Developed for a **scoped target: English Wikipedia only, a bounded date
range** — not the full multilingual, multi-year archive, since that scope
alone already runs to hundreds of GB and isn't necessary to answer any of
the five questions. Per-source sizing lives in `docs/sources/README.md`.

**Ingestion:** pageviews can't be pre-filtered by wiki at download time
(every hourly file mixes all projects) — rsync the hourly files for the
target date range and filter after. `mediawiki_history` files are already
per-wiki, so download only the target wiki's files. The page-dump files are
one-time snapshot downloads, not a time series.

**Storage layout — bronze / silver / gold:**
- **Bronze:** raw files as downloaded, untouched, partitioned by
  `date`/`hour` where applicable — kept **transient**. Stream it (download
  one file → filter → delete → next) rather than staging the full ~500GB of
  raw pageviews at once; this is the single biggest lever on local disk
  pressure.
- **Silver:** parsed, schema-applied, filtered Parquet (Snappy), partitioned
  by `date` (pageviews) or by `wiki` (the dimension tables).
- **Gold:** not Parquet — one Vega-Lite JSON chart spec per question (see
  `docs/arch/layered-design.md`'s "Gold is a chart spec, not a table").
  Small enough (KBs–low MBs) that file format/partitioning isn't a concern
  here the way it is for bronze/silver.
- Same layout works unchanged on local disk or cloud object storage
  (`s3a://`/`gs://`) — only the path prefix and cluster config differ.
- Coalesce outputs to a sane file count before writing — the small-file
  problem is real once pageviews is filtered to one wiki and split by daily
  partitions.

**Orchestration:** batch, historical, not incremental/streaming — an
ordered script invoking `spark-submit` per stage (bronze→silver→gold, per
source) is sufficient; see [`layered-design.md`](layered-design.md)'s
"Deliberately not doing" for why this doesn't need a scheduler.

**Local → cloud scaling path:**
1. Validate the entire pipeline locally, in Spark local mode, against a
   narrow slice (one wiki, one or two months).
2. Re-point input/output paths to the university's cloud object storage,
   adjust executor/memory config, and rerun the same jobs unchanged for the
   full scoped date range. Code should not need to change between the two —
   if it does, the local dev slice wasn't representative enough.
