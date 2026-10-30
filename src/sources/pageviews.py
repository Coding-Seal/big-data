"""
Pageviews source module: download hourly files, filter to the configured
domain codes and main-namespace articles, produce the `pageviews_fact`
silver table.

See docs/sources/pageviews.md for format/size facts and
docs/arch/layered-design.md for the source-module contract this
implements (describe / download / to_silver).
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from common.http import fetch_to
from common.namespaces import NON_ARTICLE_REGEX
from config import DateRange

URL_TMPL = (
    "https://dumps.wikimedia.org/other/pageviews/{yyyy}/{yyyy}-{mm}/"
    "pageviews-{yyyymmdd}-{hh}0000.gz"
)

log = logging.getLogger(__name__)


def describe() -> dict:
    return {
        "name": "pageviews",
        "format": "gzip, space-delimited, not splittable",
        "partitioning": "one file per UTC hour",
    }


def _hours(start: str, end: str):
    """[start, end] inclusive, as datetimes, one per hour."""
    start_dt, end_dt = DateRange(start, end).bounds()
    while start_dt <= end_dt:
        yield start_dt
        start_dt += timedelta(hours=1)


def _filename(hour: datetime) -> str:
    return f"pageviews-{hour.strftime('%Y%m%d')}-{hour.hour:02d}0000.gz"


def download(start: str, end: str, dest: Path) -> list[Path]:
    """Fetch hourly files for [start, end] (inclusive, "%Y-%m-%dT%H").

    Resumable: a file already present in `dest` is skipped, so calling this
    again with a later `end` only fetches what's new.
    """
    dest.mkdir(parents=True, exist_ok=True)

    fetched = []
    for hour in _hours(start, end):
        path = dest / _filename(hour)
        if path.exists():
            log.info("skip (already have) %s", path.name)
        else:
            url = URL_TMPL.format(
                yyyy=f"{hour.year:04d}", mm=f"{hour.month:02d}",
                yyyymmdd=hour.strftime("%Y%m%d"), hh=f"{hour.hour:02d}",
            )
            log.info("fetching %s", path.name)
            fetch_to(url, path)
        fetched.append(path)
    return fetched


def to_silver(
    spark: SparkSession,
    bronze_dir: Path,
    wiki: str,
    domain_codes: list[str],
    start: str,
    end: str,
) -> DataFrame:
    """Parse bronze pageviews files for [start, end] into `pageviews_fact`:
    wiki, domain_code, page_title, date, hour, views

    Reads the hours the date range names, not everything in `bronze_dir`.
    The hourly files cover every Wikimedia project at once, so the bronze
    directory is shared by every config profile (pipeline/storage.py) and
    can easily hold hours outside this window.
    """
    wanted = {_filename(hour) for hour in _hours(start, end)}
    files = sorted(p for p in bronze_dir.glob("pageviews-*.gz") if p.name in wanted)
    if not files:
        raise FileNotFoundError(
            f"no bronze pageviews files for {start}..{end} in {bronze_dir}"
        )
    missing = sorted(wanted - {p.name for p in files})
    if missing:
        # Not fatal: a partial window still answers most questions, but the
        # gap changes what Q3/Q5 mean, so it shouldn't pass silently.
        log.warning(
            "pageviews: %d of %d hour(s) in %s..%s missing from %s (first: %s) -- "
            "run `download` to fill the gap",
            len(missing), len(wanted), start, end, bronze_dir, missing[0],
        )

    raw = spark.read.text([str(f) for f in files]).withColumn(
        "source_file", F.input_file_name()
    )
    parts = F.split(F.col("value"), " ")
    parsed = raw.filter(F.size(parts) == 4).select(
        parts.getItem(0).alias("domain_code"),
        parts.getItem(1).alias("page_title"),
        parts.getItem(2).cast("long").alias("views"),
        F.regexp_extract(
            F.col("source_file"), r"pageviews-(\d{8}-\d{6})\.gz", 1
        ).alias("file_stamp"),
    )

    return (
        parsed.filter(F.col("domain_code").isin(domain_codes))
        .filter(~F.col("page_title").rlike(NON_ARTICLE_REGEX))
        .filter(F.col("page_title") != "-")
        .withColumn("date", F.substring("file_stamp", 1, 8))
        .withColumn("hour", F.substring("file_stamp", 10, 2))
        # A real timestamp, so nothing downstream has to rebuild one out of
        # date + hour. That looks trivial and isn't: date and hour are the
        # *partition* columns, and Parquet partition discovery type-infers
        # them back as integers, so `hour=08` returns 8 and a naive
        # concat(date, hour) yields "202610068" -- which parses fine for
        # hours 10-23 and throws for 00-09.
        .withColumn("ts", F.to_timestamp("file_stamp", "yyyyMMdd-HHmmss"))
        .withColumn("wiki", F.lit(wiki))
        .drop("file_stamp")
    )
