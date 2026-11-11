# Distributable image: bakes in the pipeline so a teammate without
# devenv/Nix can reproduce results with `docker build` + `docker run`.
# Same "plain uv" path AGENTS.md documents for bare metal (JDK 17 + uv,
# uv manages the pinned Python 3.11 itself) -- just containerized instead
# of installed on the host.
FROM eclipse-temurin:17-jre-jammy
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
RUN curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh \
      | bash -s -- --to /usr/local/bin

WORKDIR /app

# Dependencies first so editing src/ doesn't bust this layer's cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .

ENV PYSPARK_PYTHON=python3 \
    PATH="/app/.venv/bin:${PATH}"

# Mount a host directory here to get bronze/silver/gold out of the
# container, e.g.:
#   docker run --rm -v "$(pwd)/data:/app/data" big-data
ENTRYPOINT ["just"]
CMD ["pipeline::all"]
