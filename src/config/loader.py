"""Typed config loading -- turns config.yaml into a `Config`, so the rest
of the pipeline works with attributes instead of untyped dict keys.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

# How `date_range.start` / `.end` are spelled in config.yaml: whole hours,
# e.g. "2026-09-14T00". Both bounds are inclusive.
HOUR_FORMAT = "%Y-%m-%dT%H"


@dataclass(frozen=True)
class DateRange:
    start: str
    end: str

    def bounds(self) -> tuple[datetime, datetime]:
        """(start, end) as datetimes, both inclusive.

        One place parses the config's hour strings, so the hours a source
        *downloads* and the hours a question *reads* can't drift apart.
        """
        start_dt = datetime.strptime(self.start, HOUR_FORMAT)
        end_dt = datetime.strptime(self.end, HOUR_FORMAT)
        if end_dt < start_dt:
            raise ValueError(f"end {self.end} must not be before start {self.start}")
        return start_dt, end_dt


@dataclass(frozen=True)
class PageviewsConfig:
    domain_codes: list[str]


@dataclass(frozen=True)
class PageDumpConfig:
    wiki_db: str


@dataclass(frozen=True)
class MediawikiHistoryConfig:
    # Optional: the wiki's "In the news" style page (e.g.
    # "Wikipedia:In_the_news" on enwiki), used as Q2's news timeline. Not
    # every wiki maintains one -- see docs/sources/wikinews-itn.md.
    itn_page_title: str | None


@dataclass(frozen=True)
class Config:
    wiki: str
    storage_root: str
    pageviews: PageviewsConfig
    page_dump: PageDumpConfig
    mediawiki_history: MediawikiHistoryConfig
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
        mediawiki_history=MediawikiHistoryConfig(
            itn_page_title=raw.get("mediawiki_history", {}).get("itn_page_title")
        ),
        date_range=DateRange(
            start=raw["date_range"]["start"], end=raw["date_range"]["end"]
        ),
        gold=dict(raw.get("gold", {})),
    )
