# Ergonomic wrappers around src/run.py. Uses devenv if it's on PATH, otherwise
# plain uv -- same dual-path rule as AGENTS.md "Environment": don't assume
# devenv is installed.
uv := `command -v devenv >/dev/null 2>&1 && echo "devenv shell -- uv" || echo "uv"`
py := uv + " run python3"

# List available recipes
default:
    @just --list

# Install/update Python dependencies
sync:
    {{uv}} sync

# Fetch bronze data for the configured wiki/date range (config.yaml).
# Resumable: already-downloaded files are skipped, so widening
# date_range.end and re-running only fetches what's new.
download:
    {{py}} src/run.py download

# Parse bronze into the silver tables. Safe to re-run after `just download`
# fetches more hours -- see common/spark.py's dynamic partition overwrite.
build-silver:
    {{py}} src/run.py build-silver

# Run one question module against silver and print the result, e.g.
# `just question q1_topic_time` -- for inspection, doesn't write anything
question name:
    {{py}} src/run.py run-question {{name}}

# Run every question, write each as a Vega-Lite chart spec (data/gold/*.json).
# Change a chart's type via config.yaml's `gold:` section, not code.
gold:
    {{py}} src/run.py build-gold

# download -> build-silver -> gold, in one shot
all: download build-silver gold

# Remove silver tables (bronze is left alone -- re-run `build-silver` to rebuild)
clean-silver:
    rm -rf data/silver

# Remove gold chart specs (silver is left alone -- re-run `just gold` to rebuild)
clean-gold:
    rm -rf data/gold
