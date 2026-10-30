"""
Q4: correlation of article length and revision count with pageview volume.

Buckets by length (the x axis); revision count rides along as
avg_revisions in the tooltip rather than a second visual channel, since
the chart stays a single length_bucket -> avg_views bar either way.

The population is **every** article in page_dim, not just the ones that
were viewed. That distinction turned out to be the whole answer: an
earlier version inner-joined pageviews to page_dim, which conditions the
question on "was this article opened at all" and reports views per
*viewed* article. On the 2026-10-04 simplewiki slice that collapsed a 20x
length effect (0.015 -> 0.303 avg views across the buckets) into a 1.9x
one (1.15 -> 2.15), because length mostly predicts *whether* an article
gets opened, not how often an already-opened one does. Both readings are
now emitted: avg_views over all articles, pct_viewed, and
avg_views_if_viewed = avg_views / pct_viewed.
"""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from common.pages import with_page_id

LENGTH_BUCKETS = ["<1KB", "1-5KB", "5-20KB", "20KB+"]


def required_tables() -> list[str]:
    return ["pageviews_fact", "page_dim", "revision_dim", "redirect_dim"]


def chart_encoding() -> dict:
    return {
        "x": {
            "field": "length_bucket", "type": "ordinal", "title": "Article length",
            "sort": LENGTH_BUCKETS,
        },
        "y": {"field": "avg_views", "type": "quantitative"},
        "tooltip": [
            {"field": "length_bucket"}, {"field": "avg_views"},
            {"field": "pct_viewed"}, {"field": "avg_views_if_viewed"},
            {"field": "avg_length"}, {"field": "avg_revisions"}, {"field": "articles"},
        ],
    }


def default_mark() -> str:
    return "bar"


def run(tables: dict[str, DataFrame]) -> DataFrame:
    return aggregate(
        tables["pageviews_fact"],
        tables["page_dim"],
        tables["revision_dim"],
        tables["redirect_dim"],
    )


def aggregate(
    pageviews: DataFrame,
    page_dim: DataFrame,
    revision_dim: DataFrame,
    redirect_dim: DataFrame,
) -> DataFrame:
    """Shared with q4b_length_no_mainpage, which passes a narrowed
    page_dim/redirect_dim rather than reimplementing any of this.

    page_dim is both the population and the join source here, so removing an
    article from it removes it from the denominator too -- which is the
    point of the variant.
    """
    # Group by page_id, not page_title: with_page_id folds every redirect
    # onto the article it points at, so one article can arrive under
    # several titles.
    per_article_views = (
        with_page_id(pageviews, page_dim, redirect_dim)
        .groupBy("page_id")
        .agg(F.sum("views").alias("total_views"))
    )

    # Left join *from* page_dim: an article nobody opened during the window
    # is a real observation worth 0 views, not a missing row.
    articles = page_dim.join(per_article_views, "page_id", "left").withColumn(
        "total_views", F.coalesce("total_views", F.lit(0))
    )

    # Left join again: a page with no edits in the downloaded
    # mediawiki_history window (see sources/mediawiki_history.py) still
    # belongs in a length bucket, just with a null revision_count.
    with_revisions = articles.join(
        revision_dim.select("page_id", "revision_count"), "page_id", "left"
    )

    bucketed = with_revisions.withColumn(
        "length_bucket",
        F.when(F.col("length") < 1000, "<1KB")
        .when(F.col("length") < 5000, "1-5KB")
        .when(F.col("length") < 20000, "5-20KB")
        .otherwise("20KB+"),
    )
    return (
        bucketed.groupBy("length_bucket")
        .agg(
            F.count("*").alias("articles"),
            F.avg("total_views").alias("avg_views"),
            F.avg((F.col("total_views") > 0).cast("double")).alias("pct_viewed"),
            F.avg("length").alias("avg_length"),
            F.avg("revision_count").alias("avg_revisions"),
        )
        .withColumn("avg_views_if_viewed", F.col("avg_views") / F.col("pct_viewed"))
        .orderBy("avg_length")
    )
