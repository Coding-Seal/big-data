"""
Q4 (length half only): correlation of article length with pageview volume.

The revision-count half needs sources/mediawiki_history.py, not yet
written -- see docs/arch/implementation-order.md, steps 4 and 6.
"""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def required_tables() -> list[str]:
    return ["pageviews_fact", "page_dim"]


def chart_encoding() -> dict:
    return {
        "x": {
            "field": "length_bucket", "type": "ordinal", "title": "Article length",
            "sort": ["<1KB", "1-5KB", "5-20KB", "20KB+"],
        },
        "y": {"field": "avg_views", "type": "quantitative"},
        "tooltip": [
            {"field": "length_bucket"}, {"field": "avg_views"},
            {"field": "avg_length"}, {"field": "articles"},
        ],
    }


def default_mark() -> str:
    return "bar"


def run(tables: dict[str, DataFrame]) -> DataFrame:
    pageviews = tables["pageviews_fact"]
    page_dim = tables["page_dim"]

    per_article_views = pageviews.groupBy("page_title").agg(
        F.sum("views").alias("total_views")
    )
    joined = per_article_views.join(
        page_dim, per_article_views.page_title == page_dim.page_title
    ).select(page_dim.page_id, page_dim.length, "total_views")

    bucketed = joined.withColumn(
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
            F.avg("length").alias("avg_length"),
        )
        .orderBy("avg_length")
    )
