# Layered design

```
src/
  sources/          -- one module per raw dataset; owns download + parsing
    pageviews.py          (implemented)
    page_dump.py          (implemented; page + categorylinks + linktarget)
    mediawiki_history.py  [not yet written]
    wikidata.py            [new]
    clickstream.py         [new]

  common/           -- shared plumbing, imported by sources and questions
    sqldump.py             (MySQL INSERT parser; originally ported from poc/,
                             since fixed for a real multi-line dump format)
    spark.py               (SparkSession bootstrap, one place to change master/config)
    namespaces.py          (namespace-prefix filtering constants)
    http.py                (download-with-retry helper)
    logging.py             (logging setup, call once from run.py)
    charts.py              (result DataFrame + encoding + mark -> Vega-Lite spec)

  config/           -- typed config.yaml loading (dataclasses, not raw dicts)
    loader.py

  questions/        -- one module per research question
    q1_topic_time.py        (implemented)
    q4_length_revisions.py  (implemented, length half only)
    q2_spikes_news.py       [not yet written]
    q3_decay.py             [not yet written]
    q5_weekday.py           [not yet written]
    (q6...)         -- new questions land here only

  run.py            -- thin CLI: build silver, run a question, or build gold

silver/           -- NOT code -- the stable schema contract, documented once
  pageviews_fact(wiki, domain_code, page_title, date, hour, views)
  page_dim(wiki, page_id, page_title, namespace, length, is_redirect)
  category_dim(wiki, page_id, category)          [or topic_dim once Wikidata lands]
  revision_dim(wiki, page_id, revision_count, first_edit_ts, last_edit_ts)
  clickstream_fact(wiki, month, referrer, target_page, referrer_type, n)   [new]

gold/             -- NOT code -- one Vega-Lite JSON chart spec per question
  <question_name>.json   (data + encoding from the question module, mark
                           from config.yaml's `gold:` section or the
                           module's default_mark())

config.yaml       -- wiki(s), date range, storage root, per-question chart-type overrides
justfile          -- ergonomic wrappers: `just download`, `just build-silver`, `just question <name>`, `just gold`
```

`config.yaml` lives at the repo root (it's configuration, not code); `src/`
holds everything importable. Run via `just download` /
`just build-silver` / `just question <name>`, or directly with
`uv run python3 src/run.py <command>`.

## The contract that makes this extensible

Every **source module** implements the same three-function interface:

```
describe()                          -> metadata (name, format, partition scheme)
download(date_range, dest)          -> raw files land in bronze/
to_silver(spark, bronze_path)       -> DataFrame in the documented silver schema
```

Every **question module** implements:

```
required_tables()                   -> e.g. ["pageviews_fact", "category_dim"]
run(tables: dict[str, DataFrame])   -> a small, already chart-sized result DataFrame
chart_encoding()                    -> Vega-Lite encoding: which fields map to which visual channels
default_mark()                      -> Vega-Lite mark name (e.g. "bar") if config.yaml doesn't override it
```

`run.py` discovers question modules (directory scan or a simple registry
dict), loads only the silver tables each one declares needing, and
executes it. This is the actual mechanism behind "add a question without
touching the system": a new file in `questions/`, nothing else.

**Gold is a chart spec, not a table.** `run.py build-gold` runs every
question, turns its result into a Vega-Lite JSON spec (`common/charts.py`),
and writes `data/gold/<question>.json`. Encoding (which fields are x/y/
color/tooltip) is the question's own concern, declared in code; *mark*
(the chart type) is deliberately **config**, overridable per-question in
`config.yaml`'s `gold:` section without touching any module — see
`config.yaml`'s comments. Nothing here commits to a renderer: the same
spec works as a static image or (via vega-embed) a fully interactive chart
with zero backend, so how these actually get displayed can be decided
later.

A result must already be small/aggregated before it reaches
`chart_encoding()` — e.g. `q1_topic_time` caps itself to its top 15
categories by views; the first version return all ~22K categories in
`category_dim` and produced an unrenderable 29K-row, 3.7MB spec. Capping
is the question module's job (it knows its own data's shape), not
something the gold step or chart type can fix.

See [`extending-with-new-sources.md`](extending-with-new-sources.md) for
which additional sources plug into this same shape.

## Why this specific split

- **Silver is the seam.** As long as `pageviews_fact`/`page_dim`/etc. keep
  their schema, question code never needs to know whether the data came
  from an English or Simple English wiki, one hour or one year, local disk
  or cloud object storage. This is the single most important boundary —
  everything else follows from protecting it.
- **A new source only extends the contract, never modifies it.** Adding
  Wikidata means adding `topic_dim` alongside `category_dim`, not changing
  `category_dim` — existing questions built against `category_dim` keep
  working untouched while new ones can prefer the better table.
- **Config, not code, controls scope.** Which wiki(s), which date range,
  local vs. cloud storage root — all of this lives in `config.yaml`. Moving
  from the local dev slice to the full university-cloud run is a config
  change — see [`ingestion-storage.md`](ingestion-storage.md)'s
  local→cloud scaling path.

## Deliberately not doing

- **No Airflow/scheduler** — `run.py` sequencing bronze→silver→questions is
  enough for a batch, non-incremental pipeline; a scheduler solves a
  problem this project doesn't have.
- **No Delta/Iceberg** — silver tables are append-only or snapshot
  dimensions, never upserted, so plain partitioned Parquet is sufficient.
- **No plugin auto-loading magic** (entry points, dynamic imports off
  strings) — a plain Python dict registering question modules by name is
  enough; anything fancier is complexity the assignment doesn't need.
