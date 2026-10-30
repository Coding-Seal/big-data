"""Silver stage: bronze parsed into the typed tables questions read.

The schema here is the seam between sources and questions -- see
docs/arch/layered-design.md. The three build steps are separate and
individually callable on purpose: each takes tens of minutes on enwiki, and
a run that dies partway should be resumed one step at a time, not restarted.
"""
import logging
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from common.spark import get_spark
from config import Config
from sources import mediawiki_history, page_dump, pageviews

from .storage import bronze_dir, silver_dir

log = logging.getLogger(__name__)

PAGE_DIMS = ("page_dim", "category_dim", "redirect_dim", "hidden_category_dim")
HISTORY_TABLES = ("revision_dim", "itn_edit_fact")


def build(config: Config) -> None:
    spark = get_spark("build-silver")
    build_pageviews_fact(spark, config)
    build_page_dims(spark, config)
    build_history_tables(spark, config)
    spark.stop()


def build_pageviews_fact(spark: SparkSession, config: Config) -> None:
    path = silver_dir(config) / "pageviews_fact"
    fact = pageviews.to_silver(
        spark,
        bronze_dir(config) / "pageviews",
        config.wiki,
        config.pageviews.domain_codes,
        config.date_range.start,
        config.date_range.end,
    )
    fact.write.mode("overwrite").partitionBy("date", "hour").parquet(str(path))

    # Counted windowed: dynamic overwrite leaves any previous date_range's
    # partitions in place, which an unfiltered count would include.
    written = window_to_range(spark.read.parquet(str(path)), config)
    log.info("pageviews_fact: %s rows -> %s", f"{written.count():,}", path)


def build_page_dims(spark: SparkSession, config: Config) -> None:
    silver = silver_dir(config)
    dims = page_dump.to_silver(
        spark, bronze_dir(config) / config.page_dump.wiki_db, config.wiki
    )
    for name in PAGE_DIMS:
        path = silver / name
        dims[name].write.mode("overwrite").parquet(str(path))
        log.info("%s: %s rows -> %s", name, f"{_row_count(spark, path):,}", path)


def build_history_tables(spark: SparkSession, config: Config) -> None:
    silver = silver_dir(config)
    history = mediawiki_history.to_silver(
        spark,
        bronze_dir(config) / "mediawiki_history" / config.page_dump.wiki_db,
        config.wiki,
        config.mediawiki_history.itn_page_title,
    )
    counts = {}
    for name in HISTORY_TABLES:
        path = silver / name
        history[name].write.mode("overwrite").parquet(str(path))
        counts[name] = _row_count(spark, path)
        log.info("%s: %s rows -> %s", name, f"{counts[name]:,}", path)

    if counts["itn_edit_fact"] == 0 and config.mediawiki_history.itn_page_title:
        _warn_no_itn_edits(config)


def read_tables(
    spark: SparkSession, module, config: Config
) -> dict[str, DataFrame]:
    """A question's `required_tables()`, with `pageviews_fact` windowed to
    `date_range` -- silver can hold more windows than the config asks for
    (AGENTS.md). Dimension tables are snapshots and read whole."""
    silver = silver_dir(config)
    tables = {}
    for table in module.required_tables():
        df = spark.read.parquet(str(silver / table))
        tables[table] = window_to_range(df, config) if table == "pageviews_fact" else df
    return tables


def window_to_range(pageviews_fact: DataFrame, config: Config) -> DataFrame:
    start_dt, end_dt = config.date_range.bounds()
    # `date` is an int partition column, so this prunes whole directories
    # before reading; the `ts` bound trims the part-hours at each end.
    return pageviews_fact.filter(
        F.col("date").between(
            int(start_dt.strftime("%Y%m%d")), int(end_dt.strftime("%Y%m%d"))
        )
    ).filter(F.col("ts").between(F.lit(start_dt), F.lit(end_dt)))


def _row_count(spark: SparkSession, path: Path) -> int:
    """From the written Parquet, not the source frame: the source isn't
    cached, so counting it re-parses every bronze file again (AGENTS.md)."""
    return spark.read.parquet(str(path)).count()


def _warn_no_itn_edits(config: Config) -> None:
    """Configured but empty means Q2 can only answer "no ITN data" -- which
    should not be discovered by reading a chart later."""
    log.warning(
        "itn_edit_fact is empty but itn_page_title=%r is set: check the title "
        "against the dump's page_namespace/page_title columns, and that the "
        "snapshot covers %s..%s (see docs/sources/mediawiki-history.md)",
        config.mediawiki_history.itn_page_title,
        config.date_range.start,
        config.date_range.end,
    )
