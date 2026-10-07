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


def download(start: str, end: str, dest: Path) -> list[Path]:
    """Fetch hourly files for [start, end] (inclusive, "%Y-%m-%dT%H").

    Resumable: a file already present in `dest` is skipped, so calling this
    again with a later `end` only fetches what's new.
    """
    dest.mkdir(parents=True, exist_ok=True)
    start_dt = datetime.strptime(start, "%Y-%m-%dT%H")
    end_dt = datetime.strptime(end, "%Y-%m-%dT%H")
    if end_dt < start_dt:
        raise ValueError("end must not be before start")

    fetched = []
    hour = start_dt
    while hour <= end_dt:
        yyyymmdd = hour.strftime("%Y%m%d")
        hh = f"{hour.hour:02d}"
        path = dest / f"pageviews-{yyyymmdd}-{hh}0000.gz"
        if path.exists():
            log.info("skip (already have) %s", path.name)
        else:
            url = URL_TMPL.format(
                yyyy=f"{hour.year:04d}", mm=f"{hour.month:02d}",
                yyyymmdd=yyyymmdd, hh=hh,
            )
            log.info("fetching %s", path.name)
            fetch_to(url, path)
        fetched.append(path)
        hour += timedelta(hours=1)
    return fetched


def to_silver(
    spark: SparkSession, bronze_dir: Path, wiki: str, domain_codes: list[str]
) -> DataFrame:
    """Parse bronze pageviews files into `pageviews_fact`:
    wiki, domain_code, page_title, date, hour, views
    """
    files = sorted(bronze_dir.glob("pageviews-*.gz"))
    if not files:
        raise FileNotFoundError(f"no bronze pageviews files in {bronze_dir}")

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
        .withColumn("wiki", F.lit(wiki))
        .drop("file_stamp")
    )
