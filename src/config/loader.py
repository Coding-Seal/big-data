"""Typed config loading -- turns config.yaml into a `Config`, so the rest
of the pipeline works with attributes instead of untyped dict keys.
"""
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DateRange:
    start: str
    end: str


@dataclass(frozen=True)
class PageviewsConfig:
    domain_codes: list[str]


@dataclass(frozen=True)
class PageDumpConfig:
    wiki_db: str


@dataclass(frozen=True)
class Config:
    wiki: str
    storage_root: str
    pageviews: PageviewsConfig
    page_dump: PageDumpConfig
    date_range: DateRange
    # question name -> Vega-Lite mark override (e.g. {"q4_length_revisions":
    # "line"}). Absent entries fall back to that question's default_mark().
    # This is deliberately config, not code, so changing a chart's type
    # never means touching a question module.
    gold: dict[str, str]


def load_config(path: Path) -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Config(
        wiki=raw["wiki"],
        storage_root=raw["storage_root"],
        pageviews=PageviewsConfig(domain_codes=list(raw["pageviews"]["domain_codes"])),
        page_dump=PageDumpConfig(wiki_db=raw["page_dump"]["wiki_db"]),
        date_range=DateRange(
            start=raw["date_range"]["start"], end=raw["date_range"]["end"]
        ),
        gold=dict(raw.get("gold", {})),
    )
