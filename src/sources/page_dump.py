"""
Page dump source module: page + categorylinks + linktarget + redirect ->
`page_dim`, `category_dim` and `redirect_dim`. See docs/sources/page-dump.md
for format/schema facts and docs/arch/layered-design.md for the
source-module contract.
"""
import logging
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)

from common.dumpreader import SQLDUMP_PATH, dump_path, parse_table
from common.http import fetch_to

TABLES = ["page", "categorylinks", "linktarget", "redirect", "page_props"]
URL_TMPL = "https://dumps.wikimedia.org/{wiki_db}/latest/{wiki_db}-latest-{table}.sql.gz"
CATEGORY_NAMESPACE = 14

# Declared, not inferred: inference costs an extra sampling job, and the
# row functions below can then yield plain tuples instead of Row objects
# (which would pickle their field names once per row). Column positions come
# from the dumps' DDL -- see docs/sources/page-dump.md. All nullable, since
# `sqldump.as_int` maps a literal "NULL" to None.
PAGE_SCHEMA = StructType([
    StructField("page_id", LongType(), True),
    StructField("namespace", IntegerType(), True),
    StructField("page_title", StringType(), True),
    StructField("is_redirect", IntegerType(), True),
    StructField("length", LongType(), True),
])
CATEGORYLINKS_SCHEMA = StructType([
    StructField("cl_from", LongType(), True),
    StructField("cl_type", StringType(), True),
    StructField("cl_target_id", LongType(), True),
])
LINKTARGET_SCHEMA = StructType([
    StructField("lt_id", LongType(), True),
    StructField("lt_namespace", IntegerType(), True),
    StructField("lt_title", StringType(), True),
])
REDIRECT_SCHEMA = StructType([
    StructField("rd_from", LongType(), True),
    StructField("rd_namespace", IntegerType(), True),
    StructField("rd_title", StringType(), True),
])
# Only the first two columns of page_props; `pp_value` is a blob and
# `pp_sortkey` a float, and neither is needed to answer "is this category
# hidden". Reading just the leading fields also keeps the binary blobs out
# of the rows -- sqldump's state machine parses past them correctly, but
# there is no reason to carry them.
PAGE_PROPS_SCHEMA = StructType([
    StructField("pp_page", LongType(), True),
    StructField("pp_propname", StringType(), True),
])

# MediaWiki marks a tracking category by setting __HIDDENCAT__ on the
# category page, which the dumps expose as this page property. It is the
# structural version of "is this a maintenance category" -- the name-pattern
# heuristic it replaced needed two measured rounds and still leaked (see
# common/categories.py).
HIDDENCAT_PROP = "hiddencat"

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


def to_silver(spark: SparkSession, bronze_dir: Path, wiki: str) -> dict[str, DataFrame]:
    """Returns {"page_dim", "category_dim", "redirect_dim",
    "hidden_category_dim"} per the silver schema in
    docs/arch/layered-design.md:
      page_dim(wiki, page_id, page_title, namespace, length, is_redirect)
      category_dim(wiki, page_id, category)
      redirect_dim(wiki, from_title, to_page_id, to_title)
      hidden_category_dim(wiki, category)
    """
    sc = spark.sparkContext
    sc.addPyFile(str(SQLDUMP_PATH))
    from sqldump import as_int, as_str  # noqa: E402 -- shipped above, not importable at module level

    page_rows = parse_table(
        sc, dump_path(bronze_dir, "page"), "page",
        lambda f: (
            as_int(f[0]), as_int(f[1]), as_str(f[2]), as_int(f[3]), as_int(f[9]),
        ),
    )
    # Read twice below (page_dim keeps the articles, redirect_dim needs the
    # redirect pages the same dump holds), and re-reading means re-parsing
    # the whole gzip -- 2.39GB of it on enwiki.
    page_all = spark.createDataFrame(page_rows, PAGE_SCHEMA).persist()
    page_dim = page_all.filter("namespace = 0 AND is_redirect = 0").withColumn(
        "wiki", F.lit(wiki)
    )

    cl_rows = parse_table(
        sc, dump_path(bronze_dir, "categorylinks"), "categorylinks",
        lambda f: (as_int(f[0]), as_str(f[4]), as_int(f[6])),
    )
    cl_df = spark.createDataFrame(cl_rows, CATEGORYLINKS_SCHEMA).filter(
        "cl_type = 'page'"
    )

    lt_rows = parse_table(
        sc, dump_path(bronze_dir, "linktarget"), "linktarget",
        lambda f: (as_int(f[0]), as_int(f[1]), as_str(f[2])),
    )
    lt_df = spark.createDataFrame(lt_rows, LINKTARGET_SCHEMA).filter(
        f"lt_namespace = {CATEGORY_NAMESPACE}"
    )

    category_dim = (
        cl_df.join(lt_df, cl_df.cl_target_id == lt_df.lt_id)
        .select(cl_df.cl_from.alias("page_id"), lt_df.lt_title.alias("category"))
        .withColumn("wiki", F.lit(wiki))
    )

    # redirect.sql.gz was *not* part of the linktarget migration that hit
    # categorylinks/pagelinks -- rd_title is still stored directly here.
    rd_rows = parse_table(
        sc, dump_path(bronze_dir, "redirect"), "redirect",
        lambda f: (as_int(f[0]), as_int(f[1]), as_str(f[2])),
    )
    rd_df = spark.createDataFrame(rd_rows, REDIRECT_SCHEMA).filter("rd_namespace = 0")
    redirect_pages = page_all.filter("namespace = 0 AND is_redirect = 1")

    # Joining the target title back to page_dim (is_redirect = 0) is what
    # makes to_page_id an *article*: a double redirect finds no match here
    # and drops out, which is also what a reader experiences -- MediaWiki
    # doesn't follow the second hop either, it lands you on the redirect.
    # Both sides descend from page_all, so the target side is renamed up
    # front and joined by name -- referring to `page_dim.page_id` after a
    # join like this trips Spark's ambiguous-self-join check.
    targets = page_dim.select(
        F.col("page_title").alias("to_title"), F.col("page_id").alias("to_page_id")
    )
    redirect_dim = (
        rd_df.join(redirect_pages, rd_df.rd_from == redirect_pages.page_id)
        .select(
            redirect_pages.page_title.alias("from_title"),
            rd_df.rd_title.alias("to_title"),
        )
        .join(targets, "to_title")
        .select("from_title", "to_page_id", "to_title")
        .withColumn("wiki", F.lit(wiki))
    )

    # Hidden ("tracking") categories. The flag lives on the *category page*
    # -- a namespace-14 row in the same page dump -- not on the articles, so
    # this is page_props filtered to hiddencat, joined to those pages to
    # recover the titles that category_dim.category actually holds. Both
    # sides spell titles the same way (underscores, from lt_title/page_title),
    # so the result joins straight onto category_dim.
    pp_rows = parse_table(
        sc, dump_path(bronze_dir, "page_props"), "page_props",
        lambda f: (as_int(f[0]), as_str(f[1])),
    )
    pp_df = spark.createDataFrame(pp_rows, PAGE_PROPS_SCHEMA).filter(
        F.col("pp_propname") == HIDDENCAT_PROP
    )
    category_pages = page_all.filter(f"namespace = {CATEGORY_NAMESPACE}")
    hidden_category_dim = (
        pp_df.join(category_pages, pp_df.pp_page == category_pages.page_id)
        .select(category_pages.page_title.alias("category"))
        .distinct()
        .withColumn("wiki", F.lit(wiki))
    )

    log.info(
        "page_dump: parsed page_dim, category_dim, redirect_dim and "
        "hidden_category_dim from %s",
        bronze_dir,
    )
    return {
        "page_dim": page_dim,
        "category_dim": category_dim,
        "redirect_dim": redirect_dim,
        "hidden_category_dim": hidden_category_dim,
    }
