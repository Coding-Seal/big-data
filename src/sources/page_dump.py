"""
Page dump source module: page + categorylinks + linktarget -> `page_dim`
and `category_dim`. See docs/sources/page-dump.md for format/schema facts
and docs/arch/layered-design.md for the source-module contract.
"""
import logging
from pathlib import Path

from pyspark.sql import DataFrame, Row, SparkSession
from pyspark.sql import functions as F

from common.http import fetch_to

TABLES = ["page", "categorylinks", "linktarget"]
URL_TMPL = "https://dumps.wikimedia.org/{wiki_db}/latest/{wiki_db}-latest-{table}.sql.gz"
CATEGORY_NAMESPACE = 14

# Shipped to executors via addPyFile below, then imported by its plain
# top-level name (not `common.sqldump`) so the name matches on both driver
# and executors without needing to zip the whole `common` package -- the
# same approach already proven working in poc/ingest_dims.py.
_SQLDUMP_PATH = Path(__file__).resolve().parent.parent / "common" / "sqldump.py"

log = logging.getLogger(__name__)


def describe() -> dict:
    return {
        "name": "page_dump",
        "format": "raw MySQL INSERT dump (gzip) -- needs common/sqldump.py",
        "partitioning": "one-time snapshot per wiki, not a time series",
    }


def download(wiki_db: str, dest: Path) -> list[Path]:
    """Fetch page/categorylinks/linktarget for `wiki_db` (e.g. "simplewiki").

    Resumable: a file already present in `dest` is skipped.
    """
    dest.mkdir(parents=True, exist_ok=True)
    paths = []
    for table in TABLES:
        path = dest / f"{table}.sql.gz"
        if path.exists():
            log.info("skip (already have) %s", path.name)
        else:
            log.info("fetching %s", path.name)
            fetch_to(URL_TMPL.format(wiki_db=wiki_db, table=table), path)
        paths.append(path)
    return paths


def _parse_table(sc, path: Path, table_name: str, row_fn):
    import sqldump  # shipped via addPyFile in to_silver()

    marker = f"INSERT INTO `{table_name}`"

    def parse_partition(lines):
        in_block = False
        for line in lines:
            if line.startswith("INSERT INTO `"):
                in_block = line.startswith(marker)
            if in_block:
                yield from (row_fn(f) for f in sqldump.parse_insert_line(line))

    # Streamed line-by-line, tracking "are we inside our table's INSERT
    # block" across lines -- these dumps split a statement's VALUES tuples
    # across multiple lines (see common/sqldump.py's docstring), so a
    # complete statement usually isn't on one line. An earlier version of
    # this used wholeTextFiles (whole file as one string) to work around
    # that and overflowed the driver JVM's heap materializing a ~30MB dump
    # as a single Java Text/String object -- not viable even at this
    # course-project's small-wiki scale, let alone enwiki's multi-GB dumps.
    # This version never holds more than one line in memory per partition.
    return sc.textFile(str(path)).mapPartitions(parse_partition)


def to_silver(spark: SparkSession, bronze_dir: Path, wiki: str) -> dict[str, DataFrame]:
    """Returns {"page_dim": DataFrame, "category_dim": DataFrame} per the
    silver schema in docs/arch/layered-design.md:
      page_dim(wiki, page_id, page_title, namespace, length, is_redirect)
      category_dim(wiki, page_id, category)
    """
    sc = spark.sparkContext
    sc.addPyFile(str(_SQLDUMP_PATH))
    from sqldump import as_int, as_str  # noqa: E402 -- see _SQLDUMP_PATH comment

    page_rows = _parse_table(
        sc, bronze_dir / "page.sql.gz", "page",
        lambda f: Row(
            page_id=as_int(f[0]), namespace=as_int(f[1]), page_title=as_str(f[2]),
            is_redirect=as_int(f[3]), length=as_int(f[9]),
        ),
    )
    page_dim = (
        spark.createDataFrame(page_rows)
        .filter("namespace = 0 AND is_redirect = 0")
        .withColumn("wiki", F.lit(wiki))
    )

    cl_rows = _parse_table(
        sc, bronze_dir / "categorylinks.sql.gz", "categorylinks",
        lambda f: Row(cl_from=as_int(f[0]), cl_type=as_str(f[4]), cl_target_id=as_int(f[6])),
    )
    cl_df = spark.createDataFrame(cl_rows).filter("cl_type = 'page'")

    lt_rows = _parse_table(
        sc, bronze_dir / "linktarget.sql.gz", "linktarget",
        lambda f: Row(lt_id=as_int(f[0]), lt_namespace=as_int(f[1]), lt_title=as_str(f[2])),
    )
    lt_df = spark.createDataFrame(lt_rows).filter(f"lt_namespace = {CATEGORY_NAMESPACE}")

    category_dim = (
        cl_df.join(lt_df, cl_df.cl_target_id == lt_df.lt_id)
        .select(cl_df.cl_from.alias("page_id"), lt_df.lt_title.alias("category"))
        .withColumn("wiki", F.lit(wiki))
    )

    log.info("page_dump: parsed page_dim and category_dim from %s", bronze_dir)
    return {"page_dim": page_dim, "category_dim": category_dim}
