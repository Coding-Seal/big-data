#!/bin/sh
set -e
# The repo is bind-mounted with no .venv of its own, and .venv itself is a
# separate named volume (see justfile's docker-dev recipe) so it isn't
# rebuilt from scratch every container start. Sync once per start, then
# hand off.
uv sync --frozen
exec "$@"
