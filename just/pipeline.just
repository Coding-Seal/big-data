# Pipeline recipes: `just pipeline::download`, `just pipeline::build-silver`,
# etc. Meant to run inside the dev container (`just docker::dev`, then these
# from the attached shell) or the distribution image's own entrypoint --
# not on bare metal, so each one checks first. Running without a container
# at all means `uv` and a JDK aren't guaranteed to be on `PATH` either; use
# `uv run python3 src/run.py <command>` directly in that case instead of
# going through `just` (see README.md "Without containers").
uv := "uv"
py := uv + " run python3"

# Which profile to run against. The default is Simple English (small, fast);
# override for the English Wikipedia profile, e.g.
#   BIG_DATA_CONFIG=config.enwiki.yaml just pipeline::all
# An env var, not a `just` variable override, because `just modname::recipe`
# overrides from the root justfile don't reach into a module's own
# variables -- confirmed directly: `just pipeline::all config=...` fails
# with "variable `config` overridden on the command line but not present
# in justfile" (it's checked against the root file, not the module).
config := env("BIG_DATA_CONFIG", "config.yaml")
run := py + " src/run.py --config " + config

_require-container:
    @test -f /.dockerenv -o -f /run/.containerenv || { \
      echo "error: pipeline recipes expect to run inside a container -- try: just docker::dev" >&2; \
      exit 1; \
    }

# Install/update Python dependencies
sync: _require-container
    {{uv}} sync

# Fetch bronze data for the configured wiki/date range.
# Resumable: already-downloaded files are skipped, so widening
# date_range.end and re-running only fetches what's new.
download: _require-container
    {{run}} download

# Parse bronze into the silver tables. Safe to re-run after `download`
# fetches more hours -- see pipeline/spark.py's dynamic partition overwrite.
build-silver: _require-container
    {{run}} build-silver

# Run one question module against silver and print the result, e.g.
# `just pipeline::question q1_topic_time` -- for inspection, doesn't write anything
question name: _require-container
    {{run}} run-question {{name}}

# Run every question, write each as a Vega-Lite chart spec
# (data/gold/<wiki>/*.json). Change a chart's type via the config file's
# `gold:` section, not code.
gold: _require-container
    {{run}} build-gold

# download -> build-silver -> gold, in one shot
all: download build-silver gold

# Remove every wiki's silver tables (bronze is left alone -- re-run
# `build-silver` to rebuild)
clean-silver: _require-container
    rm -rf data/silver

# Remove every wiki's gold chart specs (silver is left alone -- re-run
# `gold` to rebuild)
clean-gold: _require-container
    rm -rf data/gold
