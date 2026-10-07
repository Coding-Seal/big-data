"""
Q1: traffic distribution by category x time of day.

pageviews_fact only has page_title, not page_id, so page_dim is the
required bridge to join into category_dim -- not just the two tables the
architecture doc's example suggests.
"""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

# category_dim has tens of thousands of distinct categories (mostly one-off
# maintenance tags -- see docs/sources/page-dump.md). Ungated, run() returns
# one row per (category, hour) across all of them: ~29K rows for a 2-hour
# window in testing, useless as a chart no matter the mark type. Capping to
# the top-N by total views is the same pattern poc/analyze.py used
# (.show(15)) for exactly this reason.
TOP_N_CATEGORIES = 15


def required_tables() -> list[str]:
    return ["pageviews_fact", "page_dim", "category_dim"]


def chart_encoding() -> dict:
    return {
        "x": {"field": "hour", "type": "ordinal", "title": "Hour (UTC)"},
        "y": {"field": "views", "type": "quantitative"},
        "color": {"field": "category", "type": "nominal"},
        "tooltip": [
            {"field": "category"}, {"field": "hour"},
            {"field": "views"}, {"field": "articles"},
        ],
    }


def default_mark() -> str:
    return "bar"


def run(tables: dict[str, DataFrame]) -> DataFrame:
    pageviews = tables["pageviews_fact"]
    page_dim = tables["page_dim"]
    category_dim = tables["category_dim"]

    joined = pageviews.join(
        page_dim, pageviews.page_title == page_dim.page_title
    ).select(page_dim.page_id, pageviews.hour, pageviews.views)

    agg = (
        joined.join(category_dim, "page_id")
        .groupBy("category", "hour")
        .agg(
            F.sum("views").alias("views"),
            F.countDistinct("page_id").alias("articles"),
        )
    )

    top_categories = (
        agg.groupBy("category")
        .agg(F.sum("views").alias("total_views"))
        .orderBy(F.desc("total_views"))
        .limit(TOP_N_CATEGORIES)
        .select("category")
    )

    return agg.join(top_categories, "category").orderBy(F.desc("views"))
