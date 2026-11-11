# big-data

Course project ("polytech big-data"): an extensible Spark pipeline that answers research questions about Wikipedia pageview traffic by joining Wikimedia's public dumps. Grading emphasis is on software engineering quality and extensibility: answering a new question, or plugging in a new data source, should mean adding one file, not touching what already works.

## Research questions

1. Traffic distribution by topic/category × time of day
2. Traffic spikes and correlation with news events
3. Decay speed after a peak: event articles vs. evergreen articles
4. Correlation of article length / revision count with pageview volume
5. Traffic by day of week (weekday/weekend), by topic

## Status

All five questions and all three source modules (`pageviews`, `page_dump`, `mediawiki_history`) are implemented in `src/` per `docs/arch/layered-design.md`, and run end-to-end against real downloaded data: `just pipeline::all` produces `data/gold/<wiki>/*.json`, one Vega-Lite chart spec per question.

Two profiles ship: `config.yaml` (Simple English, small and fast) and `config.enwiki.yaml` (English Wikipedia). Q2 only produces signal on the latter, because simplewiki has no maintained "In the news" page (`docs/sources/wikinews-itn.md`).

Known limits of the *results*, as opposed to the code: `category_dim` is raw MediaWiki categories, which are maintenance-tag dominated, so Q1's "topics" aren't really topics until a Wikidata-backed `topic_dim` lands. See `tasks.md` for what's next.

## Repo layout

```
src/
  pipeline/  -- bronze -> silver -> gold, plus SparkSession bootstrap, chart-spec building, logging setup
  config/    -- typed config.yaml loading (dataclasses, not raw dicts)
  sources/   -- one module per raw dataset: describe() / download() / to_silver(), plus retry-aware HTTP fetch and the MySQL dump parser
  questions/ -- one module per research question: required_tables() / run(), plus redirect-aware page resolution and category filtering
  run.py     -- CLI: download / build-silver / run-question / build-gold
config.yaml         -- default profile: wiki, date range, storage root, chart types
config.enwiki.yaml  -- English Wikipedia profile (`--config`, see below)
justfile            -- entry point only; recipes live in just/
just/
  pipeline.just     -- the pipeline as a just module: `just pipeline::download/build-silver/gold/all`, runs inside a container
  docker.just       -- container orchestration as a just module: `just docker::build/run/dev`, runs on the host
Dockerfile          -- distributable image: bakes in the pipeline, default CMD runs `just pipeline::all`
Dockerfile.dev      -- dev environment: toolchain only, repo bind-mounted (`just docker::dev`)
data/        -- bronze/ (shared raw downloads), silver/<wiki>/, gold/<wiki>/
docs/
  sources/   -- one file per Wikimedia dataset (location, format, size, description)
  arch/      -- system architecture, one file per concern (see docs/arch/README.md)
AGENTS.md    -- shared instructions for coding agents (Claude/Codex/opencode)
CLAUDE.md    -- imports AGENTS.md for Claude Code
pyproject.toml / uv.lock  -- uv-managed Python deps
```

See [`docs/arch/README.md`](docs/arch/README.md) for the full design (source/question module contracts, the silver schema, what was deliberately left out) and [`docs/sources/README.md`](docs/sources/README.md) for the Wikimedia datasets involved.

## Environment

Python dependency management is [uv](https://docs.astral.sh/uv/) (`pyproject.toml` / `uv.lock`) throughout. Python is pinned to 3.11, since newer Pythons break PySpark 3.5.1's `cloudpickle` serialization. Spark also needs a real JDK 17 on `PATH`.

### Containers (recommended)

`Dockerfile` and `Dockerfile.dev` build that same JDK 17 + uv + Python 3.11 environment into an image, so nobody needs a local JDK/uv install. Either Docker or Podman works; the `just` recipes below detect whichever is on `PATH`.

To run the pipeline and get results, with no build step of your own beyond the image:

```sh
just docker::build
just docker::run
# equivalent to: docker build -t big-data . && docker run --rm -v "$(pwd)/data:/app/data" big-data
```

Results land in `./data/gold/<wiki>/*.json` on the host. Override the profile the same way as a local run, e.g. `BIG_DATA_CONFIG=config.enwiki.yaml just docker::run` (set `SPARK_DRIVER_MEMORY=6g` in your shell first for the enwiki profile; both are passed through automatically). This has to be an env var, not a `just config=... ` override — `just` doesn't carry CLI variable overrides across a module boundary (`pipeline.just`'s `config` isn't visible to an override issued at the root), so `pipeline.just` reads `$BIG_DATA_CONFIG` instead.

For active development, `just docker::dev` instead starts a long-lived container with the toolchain only (no code baked in) and the repo bind-mounted, so edits on the host take effect immediately, then attaches a shell:

```sh
just docker::dev
```

`.venv` lives in a named volume kept across restarts, synced once per container start, so `just pipeline::download` / `just pipeline::build-silver` / `just pipeline::question <name>` work inside exactly like a local `uv` shell. These recipes check that they're actually running inside a container and refuse otherwise (`/.dockerenv` or `/run/.containerenv` must exist) — see "Without containers" below for running the same commands outside one.

### Without containers

Install `uv`, [`just`](https://just.systems/), and a JDK 17 yourself (`JAVA_HOME` set, `java` on `PATH`) — this repo doesn't automate that part outside a container. `pipeline.just`'s recipes are meant to run inside a container and refuse otherwise, so call `src/run.py` directly instead of going through `just`:

```sh
uv sync      # fetches Python 3.11 itself if it's not already installed
uv run python3 src/run.py download
uv run python3 src/run.py build-silver
uv run python3 src/run.py run-question q1_topic_time
```

To run the English Wikipedia profile instead, point every command at the other config: no code changes needed, and the (large) hourly pageviews files are shared with the default profile rather than downloaded twice:

```sh
uv run python3 src/run.py --config config.enwiki.yaml download
```

## Agentic development

This repo is set up to be worked on by multiple coding agents:

- `AGENTS.md` is the canonical instruction file (environment, conventions, known gotchas), read natively by Codex CLI and opencode.
- `CLAUDE.md` imports it for Claude Code.
- `.agents/skills/` has project skills for keeping `AGENTS.md` and `docs/arch/` well-maintained, launching/diagnosing Spark runs, and validating a question's output before reporting it.
