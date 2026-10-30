"""Where each stage's data lives on disk."""
from pathlib import Path

from config import Config

# config.yaml and data/ live at the repo root, two levels up from here.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _root(config: Config) -> Path:
    return REPO_ROOT / config.storage_root


def bronze_dir(config: Config) -> Path:
    """Shared across wikis: the hourly pageviews files cover every project at
    once, and dump directories are already wiki-named, so two profiles
    pointed at one storage_root reuse a single download."""
    return _root(config) / "bronze"


def silver_dir(config: Config) -> Path:
    """Per-wiki -- written with mode("overwrite"), so a shared directory
    would have enwiki's build wipe simplewiki's."""
    return _root(config) / "silver" / config.wiki


def gold_dir(config: Config) -> Path:
    return _root(config) / "gold" / config.wiki
