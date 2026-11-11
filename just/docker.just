# Container recipes: `just docker::build`, `just docker::run`, `just docker::dev`.
# docker if it's on PATH, otherwise podman -- same interface for both.
container_engine := `command -v docker >/dev/null 2>&1 && echo docker || echo podman`

# Build the distributable image (bakes in the pipeline; default CMD is
# `just pipeline::all` against config.yaml)
build:
    {{container_engine}} build -t big-data .

# Run the full pipeline in a container against the default profile, writing
# results to ./data on the host. Pass extra args to override, e.g.
#   BIG_DATA_CONFIG=config.enwiki.yaml just docker::run
run *args:
    {{container_engine}} run --rm -e SPARK_DRIVER_MEMORY -e BIG_DATA_CONFIG -v "$(pwd)/data:/app/data" big-data {{args}}

# Start (or attach to) the long-lived dev container: toolchain only, repo
# bind-mounted, .venv kept in a named volume across restarts. No
# docker-compose/podman-compose dependency -- plain run/start/exec, which
# both engines support identically.
dev:
    {{container_engine}} volume create big-data-uv-venv >/dev/null 2>&1 || true
    {{container_engine}} volume create big-data-uv-cache >/dev/null 2>&1 || true
    {{container_engine}} build -f Dockerfile.dev -t big-data-dev .
    {{container_engine}} start big-data-dev 2>/dev/null || {{container_engine}} run -d --name big-data-dev \
        -v "$(pwd):/app" -v big-data-uv-venv:/app/.venv -v big-data-uv-cache:/root/.cache/uv \
        -e SPARK_DRIVER_MEMORY -e BIG_DATA_CONFIG big-data-dev
    {{container_engine}} exec -it big-data-dev bash
