# big-data

Course project ("polytech big-data"): an extensible Spark pipeline that
answers research questions about Wikipedia pageview traffic by joining
Wikimedia's public dumps. Grading emphasis is on **software engineering
quality and extensibility** — answering a new question, or plugging in a
new data source, should mean adding one file, not touching what already
works.

## Research questions

1. Traffic distribution by topic/category × time of day
2. Traffic spikes and correlation with news events
3. Decay speed after a peak: event articles vs. evergreen articles
4. Correlation of article length / revision count with pageview volume
5. Traffic by day of week (weekday/weekend), by topic

## Status

All five questions and all three source modules (`pageviews`, `page_dump`,
`mediawiki_history`) are implemented in `src/` per
`docs/arch/layered-design.md`, and run end-to-end against real downloaded
data: `just all` produces `data/gold/<wiki>/*.json`, one Vega-Lite chart
spec per question.

Two profiles ship: `config.yaml` (Simple English — small and fast) and
`config.enwiki.yaml` (English Wikipedia). Q2 only produces signal on the
latter, because simplewiki has no maintained "In the news" page
(`docs/sources/wikinews-itn.md`).

Known limits of the *results*, as opposed to the code: `category_dim` is
raw MediaWiki categories, which are maintenance-tag dominated, so Q1's
"topics" aren't really topics until a Wikidata-backed `topic_dim` lands
(`docs/arch/extending-with-new-sources.md`). See
`docs/arch/implementation-order.md` for what's next.

## Repo layout

```
src/
  common/    -- shared plumbing (SparkSession bootstrap, sqldump parser, retry-aware HTTP fetch, logging)
  config/    -- typed config.yaml loading (dataclasses, not raw dicts)
  sources/   -- one module per raw dataset: describe() / download() / to_silver()
  questions/ -- one module per research question: required_tables() / run()
  run.py     -- CLI: download / build-silver / run-question / build-gold
config.yaml         -- default profile: wiki, date range, storage root, chart types
config.enwiki.yaml  -- English Wikipedia profile (`--config`, see below)
justfile     -- `just download`, `just build-silver`, `just question <name>`, `just gold`
data/        -- bronze/ (shared raw downloads), silver/<wiki>/, gold/<wiki>/
docs/
  sources/   -- one file per Wikimedia dataset (location, format, size, description)
  arch/      -- system architecture, one file per concern (see docs/arch/README.md)
AGENTS.md    -- shared instructions for coding agents (Claude/Codex/opencode)
CLAUDE.md    -- imports AGENTS.md for Claude Code
devenv.nix   -- optional: JDK 17 + Python 3.11 + uv via nix (NixOS/devenv users)
pyproject.toml / uv.lock  -- uv-managed Python deps (required either way)
```

See [`docs/arch/README.md`](docs/arch/README.md) for the full design
(source/question module contracts, the silver schema, what was
deliberately left out) and [`docs/sources/README.md`](docs/sources/README.md)
for the Wikimedia datasets involved.

## Environment

Python dependency management is [uv](https://docs.astral.sh/uv/)
(`pyproject.toml` / `uv.lock`) throughout. Python is pinned to 3.11 —
newer Pythons break PySpark 3.5.1's `cloudpickle` serialization. Spark also
needs a real JDK 17 on `PATH`.

**If you're on NixOS, or already have [devenv](https://devenv.sh/)
installed:**

```sh
devenv shell              # provisions JDK 17 + Python 3.11 + uv + just, runs `uv sync`
devenv shell -- just download
devenv shell -- just build-silver
devenv shell -- just question q1_topic_time
```

**Otherwise:** devenv isn't required. Install `uv`, [`just`](https://just.systems/),
and a JDK 17 yourself (`JAVA_HOME` set, `java` on `PATH`) — this repo
doesn't automate that part outside devenv — then:

```sh
uv sync      # fetches Python 3.11 itself if it's not already installed
just download
just build-silver
just question q1_topic_time
```

(`just` is only an ergonomic wrapper around `uv run python3 src/run.py
<command>` — see `justfile`; use that directly if you'd rather not install
`just`.)

To run the English Wikipedia profile instead, point every recipe at the
other config — no code changes, and the (large) hourly pageviews files are
shared with the default profile rather than downloaded twice:

```sh
just config=config.enwiki.yaml all
```

## Agentic development

This repo is set up to be worked on by multiple coding agents:

- **AGENTS.md** is the canonical instruction file (environment, conventions,
  known gotchas), read natively by Codex CLI and opencode.
- **CLAUDE.md** imports it for Claude Code.
- **`.agents/skills/`** has two project skills: one for keeping `AGENTS.md`
  itself well-maintained, one for working with `docs/arch/`.
