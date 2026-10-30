"""
Q1: traffic distribution by category x time of day -- **all** categories.

pageviews_fact only has page_title, not page_id, so page_dim is the
required bridge to join into category_dim -- not just the two tables the
architecture doc's example suggests. redirect_dim comes along for the ride
because a bare page_dim join silently drops redirect traffic
(common/pages.py).

What this measures honestly: at enwiki scale every one of the top 15
categories by views is a maintenance/tracking tag, so unfiltered this is a
chart of **template usage**, not of topics. That is a real (and reportable)
property of MediaWiki categories, which is why it stays as its own answer
-- q1b_topic_time_filtered asks the same question with the tracking tags
removed, and the pair is more informative than either alone.
"""
from pyspark.sql import DataFrame

from common.categories import views_by_category_hour

# category_dim has tens of thousands of distinct categories (mostly one-off
# maintenance tags -- see docs/sources/page-dump.md). Ungated, run() returns
# one row per (category, hour) across all of them: ~29K rows for a 2-hour
# window in testing, useless as a chart no matter the mark type.
TOP_N_CATEGORIES = 15


def required_tables() -> list[str]:
    return ["pageviews_fact", "page_dim", "category_dim", "redirect_dim"]


def chart_encoding() -> dict:
    return {
        "x": {"field": "hour", "type": "ordinal", "title": "Hour (UTC)"},
        "y": {
            "field": "views",
            "type": "quantitative",
            # An article carries many categories at once, so a view is
            # counted once per category and the series overlap. Vega-Lite
            # stacks bar+color by default, which would draw an hourly total
            # ~3.8x real traffic out of overlapping sets (common/categories.py).
            "stack": None,
        },
        "color": {"field": "category", "type": "nominal"},
        "tooltip": [
            {"field": "category"}, {"field": "hour"},
            {"field": "views"}, {"field": "articles"},
        ],
    }


def default_mark() -> str:
    return "bar"


def run(tables: dict[str, DataFrame]) -> DataFrame:
    return views_by_category_hour(
        tables["pageviews_fact"],
        tables["page_dim"],
        tables["category_dim"],
        tables["redirect_dim"],
        top_n=TOP_N_CATEGORIES,
        drop_hidden=False,
    )
