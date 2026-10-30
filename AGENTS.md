# Agent instructions

This file is the shared instruction set for any coding agent working in this
repo — Claude Code, Codex CLI, opencode, or others. `CLAUDE.md` imports this
file verbatim; don't fork Claude-specific instructions into a separate file,
add a `## Claude Code notes` section below instead if something is truly
tool-specific.

## What this project is

A course project ("polytech big-data"): an extensible pipeline that answers
research questions about Wikipedia pageview traffic (topic/time patterns,
spikes vs. news, decay after peaks, length/revision correlation,
weekday/weekend patterns) using Spark over Wikimedia's public dumps. Grading
emphasis is **software engineering quality and extensibility** — answering a
new question or adding a data source should mean adding one file, not
touching what already works. See `docs/arch/README.md` for the full
design rationale and `docs/sources/README.md` for the data sources
themselves (one file per source: location, format, size, description).

Using Spark is an intentional assignment constraint ("serious tools, even
if overkill"), not a scale requirement — don't suggest replacing it with
pandas/dask just because a given data slice is small.

## Repo layout

- `tasks.md` — what's still outstanding, carried between sessions. **Read
  it first**: it names the next concrete step and flags anything that is
  implemented but unverified. Update it as work lands. Finished work does
  not accumulate there — durable facts go to "Known gotchas" below or to
  `docs/`, the narrative to git history.
- `docs/sources/` — one file per Wikimedia dataset (location, format,
  size, description). Read the relevant file before integrating a new
  source, and before assuming any size/format fact about an existing one.
- `docs/arch/` — system architecture, one file per concern (layered
  design, extending with new sources, implementation order,
  ingestion/storage). Read `docs/arch/README.md` first; read before
  changing the pipeline's shape.
- `src/` — the real pipeline, per `docs/arch/layered-design.md`. The code is
  laid out by stage, so where something lives says which stage it belongs
  to:
  - `pipeline/bronze.py` / `silver.py` / `gold.py` — one module per
    medallion stage, plus `storage.py` for where each stage's data lives.
    `silver.build()` is three separately callable steps
    (`build_pageviews_fact`, `build_page_dims`, `build_history_tables`) so
    a run that dies partway is resumed one step at a time.
  - `sources/` — one module per dataset, producing silver tables.
  - `questions/` — one module per research question, reading silver;
    `questions/__init__.py` holds the registry.
  - `common/` — shared helpers (`spark.py`, `pages.py`, `charts.py`,
    `dumpreader.py` + `sqldump.py` for the MySQL dumps).
  - `run.py` — CLI dispatch only, one subcommand per stage.

  Run via `just download` / `just build-silver` / `just question <name>`
  (see `justfile`), or `uv run python3 src/run.py <command>` directly.
  There is no `poc/` anymore — all five questions and all four sources are
  implemented here; new work always lands in `src/`, never in a new
  throwaway script.
- `config.yaml` — wiki(s), date range, storage root. Lives at the repo
  root, not under `src/`, since it's configuration, not code.
  `config.enwiki.yaml` is a second profile for the same pipeline
  (`run.py --config <file>`, or `just config=config.enwiki.yaml <recipe>`);
  Q2 needs it, since simplewiki has no ITN page. Bronze is shared between
  profiles, silver and gold are per-wiki (`data/silver/<wiki>/...`) — see
  `run.py::storage_paths`.
- `.agents/skills/` — shared skill docs, one per recurring task:
  `update-agents-md` and `docs-arch` (maintaining this file and the design
  docs), `running-pipeline-jobs` (launching, resuming, and diagnosing Spark
  runs — read before any enwiki run), `validating-question-output` (read
  before reporting any number a question produced). These are plain
  conventions any agent should read when doing that kind of work; Claude
  Code's own skill auto-discovery looks at `.claude/skills/` specifically,
  so don't assume they're auto-invoked there without also being registered
  under that path.

## Environment

Python dependency management is **uv** everywhere (`pyproject.toml` /
`uv.lock`) — Python is pinned to 3.11: PySpark 3.5.1's bundled
`cloudpickle` recurses infinitely serializing closures under newer Pythons
(confirmed on 3.14). Don't bump the Python version without re-checking
this. Add dependencies with `uv add <package>` (prefixed with
`devenv shell --` if using devenv), never hand-edit `uv.lock`.

There are two supported ways to actually run things — pick based on what's
available, don't assume one over the other:

- **devenv** — use this on NixOS, or anywhere `devenv` is already
  installed. `devenv shell` provisions JDK 17 and pinned Python 3.11 via
  nix, and runs `uv sync` automatically. Prefix commands:
  `devenv shell -- uv run python3 src/run.py download`. Requires both
  `languages.python.venv.enable = true` **and**
  `languages.python.uv.sync.enable = true` in `devenv.nix` — `uv.sync`
  alone runs `uv sync` but doesn't put the resulting venv on `PATH`, so
  `python3` silently resolves to the bare nix interpreter and
  `import pyspark` fails with `ModuleNotFoundError` even though sync
  reported success. First `devenv shell` in a fresh checkout needs real
  network access (flake inputs); later runs are cached.
- **plain uv** — everywhere else. devenv is not assumed to be present and
  this repo does not automate installing its prerequisites outside devenv:
  whoever is running the project is responsible for having `uv` installed
  and a JDK 17 on `PATH`/`JAVA_HOME` (Spark needs a real JVM; uv has no
  part in that). Python itself does not need to be pre-installed — `uv
  sync` fetches the pinned 3.11 automatically. Then `uv run <cmd>`, e.g.
  `uv run python3 src/run.py download`. Verified working standalone (no
  devenv, no nix wrapper) as part of setting this up.

If unsure which applies, check whether a `devenv` binary is on `PATH` (or
whether `/etc/os-release` says NixOS) before reaching for `devenv shell --`.

Spark runs `local[*]`, so executors live in the driver JVM and its heap is
the entire memory budget. The default (1g) is fine for the `simple`
profile and not for `enwiki`'s multi-GB dumps — export
`SPARK_DRIVER_MEMORY=6g` for those runs. It has to be an env var:
`local[*]` fixes the driver heap when the JVM launches, before
`SparkSession.builder.config()` is read, so setting it in code silently
does nothing (see `common/spark.py`).

## Conventions

- The silver schema documented in `docs/arch/layered-design.md` is the seam
  between data sources and research questions. Source modules only ever
  *produce* silver tables; question modules only ever *read* them — never
  let a question module reach into bronze or raw dump formats directly.
- Prefer extending the contract (new table) over modifying it (changing an
  existing table's shape) when adding a source, so existing questions keep
  working.
- No scheduler, no Delta/Iceberg, no dynamic plugin auto-discovery — these
  were deliberately rejected as unnecessary for this project's scope (see
  `docs/arch/layered-design.md`, "Deliberately not doing"). Don't
  reintroduce them speculatively.

## Known gotchas worth not re-discovering

- MySQL dump files (`page.sql.gz`, `categorylinks.sql.gz`, ...) are **not**
  classic single-mega-line mysqldump extended-insert statements — `VALUES`
  is on its own line, then one tuple per following line. A naive
  `line.find("VALUES (")` per line silently matches nothing and parses zero
  rows, no error. Don't "fix" this by reading a whole file into one string
  to reassemble statements (`SparkContext.wholeTextFiles`) either — that
  overflows the driver JVM's heap on even a small (~30MB) dump. Stream
  line-by-line, tracking which INSERT block you're in across lines (see
  `src/sources/page_dump.py::_parse_table`, `docs/sources/page-dump.md`).
- `categorylinks.sql.gz` does not store category names directly — join
  through `linktarget` (`cl_target_id` → `lt_id`), and filter
  `cl_type = 'page'` + `lt_namespace = 14`.
- `pagelinks.sql.gz` went through the same `linktarget` migration —
  `pl_target_id` → `lt_id`, no `pl_title` column anymore. Filter
  `lt_namespace = 0` to count only article-to-article links (otherwise
  template/category transclusions inflate in-degree). `redirect.sql.gz`,
  by contrast, was **not** migrated — `rd_title` is still stored directly.
- Raw MediaWiki categories are dominated by maintenance/tracking categories,
  not topics — don't treat `category_dim` as a topic taxonomy as-is.
  Measured on a real slice: 13 of Q1's top 15 categories by views are
  tracking tags, led by `Webarchive_template_wayback_links`; on the full
  enwiki week it is **15 of 15**, led by `Articles_with_short_description`
  (454M views / 2.81M articles). `common/categories.py::is_maintenance`
  filters these by name convention — a heuristic floor, not a taxonomy; the
  structural fix is `page_props.sql.gz`'s `__HIDDENCAT__` flag.
- **Category view counts are not additive.** An article carries many
  categories at once, so a view is counted once per category: on the enwiki
  week the top 15 categories sum to ~1.89B against 501.9M of real article
  traffic. Vega-Lite stacks `bar` + `color` by default, so any category
  chart must set `"stack": None` or it draws an hourly total ~3.8x reality
  out of overlapping sets. Same trap for any future "by topic" breakdown.
- Never join `pageviews_fact` to `page_dim` on `page_title` directly —
  `page_dim` is namespace-0 **non-redirect** only, so that drops every view
  that landed on a redirect (measured: 7.2% of traffic, concentrated on
  news-driven pages). Use `common/pages.py::with_page_id`, which also
  applies MediaWiki's first-letter capitalization rule, and aggregate by
  `page_id` afterwards — several titles can resolve to one article. This
  applies to a question that never touches `page_dim` at all: grouping
  `pageviews_fact` by `page_title` silently treats a redirect as its own
  article, which is the same bug wearing a different hat. All five questions
  now fold through `with_page_id` first and carry `page_title` only as a
  display column joined back from `page_dim` at the end. Note the fold also
  *drops* titles resolving to no namespace-0 page (`Special:*`, pages newer
  than the snapshot), so a question's view totals are article traffic, not
  all traffic — intended, but it means totals are not comparable with raw
  dump counts. Measured on enwiki 2026-09-14..20: 31,081,767 of 501,872,103
  views (6.2%) arrive under a non-canonical title.
- **`Main_Page` is not dropped by that fold** — it is a namespace-0
  non-redirect, so `page_dim` has it, and on the enwiki week above it is the
  single biggest article at 32,139,712 views (6.4% of all article traffic),
  arriving under 15+ title variants (`HomePage`, `Mainpage`, `Main_Pag`,
  `Main+Page`, `Mian_Page`, ...) that `with_page_id` correctly merges onto
  one `page_id`. So Q1/Q4/Q5 all count the front page as an article, and
  front-page traffic has a different weekly rhythm than reading — which is
  exactly what Q5 measures. Decide per question whether to exclude it; don't
  assume it is already gone.
- A question that averages over "articles that were viewed" is answering a
  different question than one that averages over all articles: with a short
  window, ~97% of articles have zero views, and conditioning on being
  viewed hid most of Q4's effect (20x → 1.9x). Prefer a left join *from*
  `page_dim` with a zero fill. How much this matters is profile-dependent,
  so don't over-report it: on enwiki over a full week `pct_viewed` is
  90.5–99.7% per bucket and the two readings nearly agree (71.5x vs 64.9x).
  The 20x → 1.9x collapse was a simplewiki/short-window artifact.
- **Ranking pages by absolute peak is not the same as finding spikes**, and
  Q3 does the former. Measured on the enwiki week, its top 10 by
  `peak_views` includes `Main_Page` at **1.52x** its own baseline — a flat
  diurnal curve with no decay in it, charted purely on volume — while
  excluding pages at 100–135x whose absolute peaks are smaller
  (`Indian_Institutes_of_Technology` 122x, `2018` 115x, `Peccary` 107x).
  Rank by `peak / avg` (the gate Q2 already applies) when the question is
  about spikes. Most of what survives an absolute-peak ranking at enwiki
  scale is automated traffic: single-hour impulses at 1.2–4.8% mean-of-peak,
  for which "decay after the peak" has no referent.
- **Shrinking a join's input can break the job**, which is not where you
  look for an OOM. Pre-aggregating pageviews to `(page_id, hour)` before the
  `category_dim` join (see `common/categories.py::views_by_category_hour`;
  worth ~15%, 29m40s → 25m18s on enwiki) shrank Spark's size
  estimate enough that the optimizer switched to a broadcast hash join, then
  under-predicted the materialized size and died in `BroadcastExchangeExec`
  — "Not enough memory to build and broadcast the table" — on the **simple**
  profile at the 1g default heap, where the slower un-aggregated version had
  just succeeded. The `.hint("merge")` on that join is load-bearing, not
  tuning: neither side is ever broadcast-sized (183.8M category rows against
  millions of page-hours), so the strategy is pinned rather than estimated.
  Expect this any time an optimization changes cardinality upstream of a
  big join.
- The `RowBasedKeyValueBatch: Calling spill() ... Will not spill but return
  0` warning is **not** by itself the tell for a bad shuffle config. The
  `running-pipeline-jobs` skill records it alongside
  `shuffle.partitions = 8`, but it also appears on a healthy
  `shuffle.partitions = 200` + AQE run of any Q1-class aggregation (2M
  groups with a `countDistinct`) — measured 2026-10-28. Check the partition
  count and spill volume before concluding anything from the warning alone.
- Don't raise `spark.shuffle.file.buffer` above its 32k default. It reads
  like a free win when a job is spill-bound, and it is not: at
  `shuffle.partitions=200` Spark picks `BypassMergeSortShuffleWriter`
  (chosen when partitions ≤ `spark.shuffle.sort.bypassMergeThreshold`,
  default 200), which opens **one buffered writer per partition at the same
  time**. 200 × 1m × 8 concurrent tasks ≈ 1.6GB of raw buffers, which OOMs
  the 1g default heap instantly — measured 2026-10-28, two simplewiki runs
  died in `BufferedOutputStream.<init>` under
  `DiskBlockObjectWriter.initialize`. The two settings are only dangerous
  together, so the partition count alone is fine.
- Silver can hold **more windows than the config asks for**, and questions
  used to read whole tables. `partitionOverwriteMode=dynamic` means a write
  replaces only the `(date, hour)` partitions it touches, so changing
  `date_range` and rebuilding leaves the *previous* window on disk next to
  the new one. Measured 2026-10-28: `silver/en/pageviews_fact` held the
  configured Sept 14–20 *and* a stale Oct 4–10, so Q2 reported 18 of its
  top 20 spikes as `NEWS_UNKNOWN` (true of the October hours — they fall
  past the ITN dump's coverage — and nothing to do with the question), and
  Q5's per-weekday totals were silently the sum of two different weeks.
  `run.py::load_tables` now windows `pageviews_fact` to `date_range` for
  every question, so this can't recur; deleting the stale partitions alone
  would have fixed the symptom and left the trap. Note the two profiles
  legitimately configure different weeks, so "extra partitions" is normal
  on a shared bronze — don't delete `silver/simple`'s Oct 4–10 thinking
  it's stale, that one *is* its window.
- Window length is load-bearing for Q2/Q3/Q5, and the failure is silent.
  With n hourly samples, a page's `views / avg(views)` can't exceed n, so
  any spike threshold ≥ n returns zero rows by arithmetic — Q2 looked
  "implemented but finding nothing" on a 2-hour window. Q5 needs at least
  a full week to have one of every weekday.
- `.gz` pageview files are not splittable in Spark; parallelism comes from
  file count, not intra-file splits.
- Don't rebuild a timestamp from `pageviews_fact`'s `date` + `hour` — use
  its `ts` column. Those two are *partition* columns, so Parquet partition
  discovery type-infers them back as integers: `hour=08` returns `8`, and
  `concat(date, hour)` silently yields `"202610068"`, which parses for
  hours 10–23 and throws for 00–09. A date range that happens to start at
  10:00 will never show the bug.
- `mediawiki_history` lags the pageviews dumps by weeks, and the shortfall
  is invisible unless you look: the `2026-09` snapshot was generated
  2026-10-05, and its `2026-10` file is a 1.4MB stub covering only the
  first days of October while pageviews are current to yesterday. Any
  "spike wasn't near a news edit" conclusion drawn over an uncovered hour
  is an artifact — `q2_spikes_news` therefore reports three states, and
  `NEWS_UNKNOWN` covers both this and the no-ITN-page case.
- **Q2's ±24h ITN match cannot say "no", so `NEWS_MATCHED` is not evidence.**
  The ITN page is edited ~6.6x/day, so measured on enwiki 2026-09-14..20
  (136 edits, 46 in-window) **168 of 168 hours** sit within ±24h of some
  edit — `NEWS_ABSENT` is unreachable by arithmetic and the question returns
  20/20 matched whatever the data says. Worse, the spikes' median distance
  to the nearest edit (2.45h) is indistinguishable from an arbitrary hour's
  (2.53h), so the proximity carries no information. Base rates: ±12h 92.3%,
  ±6h 76.2%, ±3h 54.8%, ±1h 28.6%. Tightening the window narrows but does
  not fix this — timestamp proximity to a page edited several times a day
  can't establish a news link; matching the spiking article against the
  articles the ITN revision *links to* is the real test.
- Relatedly, `revision_dim` only knows about pages *edited during the
  months downloaded*. Small wikis publish one all-time file so coverage is
  complete (simplewiki: 605K pages); enwiki publishes monthly files and
  only the months the date range touches are fetched, so Q4's revision
  half there covers recently-edited pages only. Don't read enwiki's
  `avg_revisions` as a whole-wiki average. The coverage is also **correlated
  with the effect**: measured per length bucket it runs 3.0% / 16.6% /
  23.7% / 43.0% from `<1KB` to `20KB+`, so the charted 43.6x revision
  gradient is partly just coverage. `avg()` skips nulls, which puts
  `avg_revisions` (covered articles only) and `avg_views` (all articles) in
  the same tooltip row on different denominators — zero-filled the gradient
  is 0.61 → 377.88.
- `mediawiki_history` dumps have no `-latest-` alias and only the last two
  monthly snapshot generations are retained (currently rolling month to
  month) — hardcoding a snapshot name in source code goes stale within a
  couple of months. `src/sources/mediawiki_history.py::download` discovers
  the current snapshot and the real per-wiki filenames from the dumps
  site's own directory listings instead. Also: small wikis (e.g.
  simplewiki) publish one `<snapshot>.<wiki>.all-time.tsv.bz2` file, not a
  monthly series the way bigger wikis do — don't assume the monthly
  filename pattern unconditionally.
- Simple English Wikipedia has no actively-maintained "In the news"
  portal — confirmed against the downloaded `simplewiki` page dump, the
  only `Current_events`-titled pages are redirects, not a live edited page.
  Q2's news correlation (`config.yaml`'s `mediawiki_history.itn_page_title`)
  needs `enwiki`, not the project's default `simple` dev config, to produce
  real signal (see `docs/sources/wikinews-itn.md`).
