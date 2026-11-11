# Entry point only -- recipes live in modules under just/:
#   just/docker.just    container orchestration, runs on the host
#   just/pipeline.just  the actual pipeline, runs inside a container
# See AGENTS.md "Environment".
mod docker "just/docker.just"
mod pipeline "just/pipeline.just"

# List available recipes
default:
    @just --list
