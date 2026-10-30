"""
Q3: how fast does traffic decay after a page's peak hour.

The decay maths is pure window/groupBy work over pageviews_fact, but it has
to run on *articles*, not on URL titles: a redirect carries its own hourly
series in pageviews_fact, so keying on page_title would chart
`Hurricane_Melissa` and a redirect pointing at it as two unrelated curves,
each peaking lower than the article actually did. page_dim/redirect_dim are
required for that fold alone (common/pages.py) -- no new source.
"""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from common.pages import with_page_id

# Same reasoning as q1's TOP_N_CATEGORIES: ungated this is one row per
# (page, hour) for every page that ever appears, most of it one-off noise.
# Capping to the top-N pages by peak views keeps the decay curve readable.
TOP_N_PAGES = 10


def required_tables() -> list[str]:
    return ["pageviews_fact", "page_dim", "redirect_dim"]


def chart_encoding() -> dict:
    return {
        "x": {"field": "hours_since_peak", "type": "quantitative", "title": "Hours since peak"},
        "y": {"field": "pct_of_peak", "type": "quantitative", "title": "% of peak views"},
        "color": {"field": "page_title", "type": "nominal"},
        "tooltip": [
            {"field": "page_title"}, {"field": "hours_since_peak"},
            {"field": "views"}, {"field": "peak_views"},
        ],
    }


def default_mark() -> str:
    return "line"


def run(tables: dict[str, DataFrame]) -> DataFrame:
    pageviews = tables["pageviews_fact"]  # carries `ts`, see sources/pageviews.py
    page_dim = tables["page_dim"]
    redirect_dim = tables["redirect_dim"]

    # Fold every title that resolves to one article into a single hourly
    # series *before* any peak maths, so a peak is the article's real peak.
    ts = (
        with_page_id(pageviews, page_dim, redirect_dim)
        .groupBy("page_id", "ts")
        .agg(F.sum("views").alias("views"))
    )

    peak_views = ts.groupBy("page_id").agg(F.max("views").alias("peak_views"))
    # Earliest hour the peak occurred, in case of a tie -- so "hours since
    # peak" counts from a single well-defined zero point per page.
    peak_ts = (
        ts.join(peak_views, "page_id")
        .filter(F.col("views") == F.col("peak_views"))
        .groupBy("page_id", "peak_views")
        .agg(F.min("ts").alias("peak_ts"))
    )

    top_pages = (
        peak_views.orderBy(F.desc("peak_views")).limit(TOP_N_PAGES).select("page_id")
    )

    decay = (
        ts.join(top_pages, "page_id")
        .join(peak_ts, "page_id")
        .withColumn(
            "hours_since_peak",
            (F.col("ts").cast("long") - F.col("peak_ts").cast("long")) / 3600,
        )
        .filter(F.col("hours_since_peak") >= 0)
        .withColumn("pct_of_peak", F.col("views") / F.col("peak_views") * 100)
    )

    # page_dim holds the canonical title; the chart colours by it, and after
    # the fold it is the only title that still names a row's subject.
    return (
        decay.join(page_dim.select("page_id", "page_title"), "page_id")
        .select(
            "page_title", "hours_since_peak", "views", "peak_views", "pct_of_peak"
        )
        .orderBy("page_title", "hours_since_peak")
    )
