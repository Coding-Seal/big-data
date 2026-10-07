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

- `docs/sources/` — one file per Wikimedia dataset (location, format,
  size, description). Read the relevant file before integrating a new
  source, and before assuming any size/format fact about an existing one.
- `docs/arch/` — system architecture, one file per concern (layered
  design, extending with new sources, PoC mapping, implementation order,
  ingestion/storage). Read `docs/arch/README.md` first; read before
  changing the pipeline's shape.
- `src/` — the real pipeline (`common/`, `sources/`, `questions/`,
  `run.py`), per `docs/arch/layered-design.md`. Run via `just download` /
  `just build-silver` / `just question <name>` (see `justfile`), or
  `uv run python3 src/run.py <command>` directly.
- `poc/` — proof-of-concept scripts that proved the bronze→silver→gold
  shape end-to-end before `src/` existed. Being superseded incrementally
  (see `docs/arch/poc-mapping.md` for what's already ported vs. still
  poc-only) — don't add new work to `poc/`, extend `src/` instead.
- `config.yaml` — wiki(s), date range, storage root. Lives at the repo
  root, not under `src/`, since it's configuration, not code.
- `.agents/skills/` — shared skill docs for maintaining this file and
  `docs/arch/`. These are plain conventions any agent should read when doing
  that kind of edit; Claude Code's own skill auto-discovery looks at
  `.claude/skills/` specifically, so don't assume they're auto-invoked
  there without also being registered under that path.

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
  `devenv shell -- uv run python3 poc/ingest.py`. Requires both
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
- `.gz` pageview files are not splittable in Spark; parallelism comes from
  file count, not intra-file splits.
