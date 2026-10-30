"""
Q2: traffic spikes vs. news -- detect spikes in pageviews_fact, then flag
which ones fall near an edit to the wiki's "In the news" style page
(itn_edit_fact, from sources/mediawiki_history.py).

Spike detection needs no new source; only the "is this near real news"
half does. Matching is a heuristic (nearest ITN edit within a time
window), not a derivable fact -- see docs/sources/wikinews-itn.md.

**"Not near news" and "no news data" are different answers** and this
module keeps them apart, because two separate things routinely leave
itn_edit_fact without an edit to match against:

  - `mediawiki_history.itn_page_title` isn't set (true for the default
    `simple` config -- simplewiki has no actively-maintained ITN page, see
    docs/sources/wikinews-itn.md), so the table is empty outright;
  - the dumps lag. mediawiki_history publishes monthly snapshots a few
    weeks behind: the 2026-09 snapshot was generated 2026-10-05 and its
    2026-10 file is a 1.4MB stub covering only the first days of October,
    while the pageviews files are current to yesterday. A window the
    history doesn't reach has no ITN edits *available*, which is not the
    same as a window with no news in it.

Collapsing either case into has_nearby_news=false would manufacture a
finding ("most spikes aren't news-driven!") out of missing data, so spikes
outside the span itn_edit_fact actually covers are labelled explicitly.
"""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from common.pages import with_page_id

# A hour counts as a "spike" for a page if its views are at least this many
# times that page's own average views over the window.
SPIKE_RATIO = 3.0
# How close (in hours) an ITN edit must be to a spike to count as "nearby".
NEWS_WINDOW_HOURS = 24
# Same reasoning as q1/q3's top-N caps.
TOP_N_SPIKES = 20

# The three answers this question can give about one spike.
NEWS_MATCHED = "near an ITN edit"
NEWS_ABSENT = "no ITN edit nearby"
NEWS_UNKNOWN = "no ITN data for this hour"


def required_tables() -> list[str]:
    return ["pageviews_fact", "itn_edit_fact", "page_dim", "redirect_dim"]


def chart_encoding() -> dict:
    return {
        "x": {"field": "ts", "type": "temporal", "title": "Spike hour"},
        "y": {"field": "views", "type": "quantitative"},
        "color": {
            "field": "news_match", "type": "nominal",
            "sort": [NEWS_MATCHED, NEWS_ABSENT, NEWS_UNKNOWN],
        },
        "tooltip": [
            {"field": "page_title"}, {"field": "ts"}, {"field": "views"},
            {"field": "avg_views"}, {"field": "hours_from_nearest_news"},
        ],
    }


def default_mark() -> str:
    return "point"


def run(tables: dict[str, DataFrame]) -> DataFrame:
    pageviews = tables["pageviews_fact"]  # carries `ts`, see sources/pageviews.py
    itn = tables["itn_edit_fact"]
    page_dim = tables["page_dim"]
    redirect_dim = tables["redirect_dim"]

    # Spike detection has to run per *article*, not per URL title. Redirect
    # traffic is 7.2% of all views and concentrated on exactly the
    # news-driven pages this question is about (common/pages.py), so keying
    # on page_title both splits one news event across several rows and
    # understates the article's real peak -- the two failure modes that
    # would most distort an answer about news.
    ts = (
        with_page_id(pageviews, page_dim, redirect_dim)
        .groupBy("page_id", "ts")
        .agg(F.sum("views").alias("views"))
    )

    baseline = ts.groupBy("page_id").agg(F.avg("views").alias("avg_views"))
    spikes = (
        ts.join(baseline, "page_id")
        .filter(F.col("avg_views") > 0)
        .filter(F.col("views") >= SPIKE_RATIO * F.col("avg_views"))
        .select("page_id", "ts", "views", "avg_views")
    )

    # mediawiki_history stores the raw event_timestamp string (e.g.
    # "2026-09-03 12:34:56.0"); truncate to whole seconds before parsing
    # since the fractional-second digit count varies row to row.
    itn_ts = itn.select(
        F.to_timestamp(F.substring("event_timestamp", 1, 19), "yyyy-MM-dd HH:mm:ss").alias(
            "news_ts"
        )
    )

    # itn_ts is tiny (one page's edit history for the downloaded window) --
    # a crossJoin against it is nowhere near pageviews_fact's scale.
    nearest_news = (
        spikes.crossJoin(itn_ts)
        .withColumn(
            "hours_from_news",
            F.abs(F.col("ts").cast("long") - F.col("news_ts").cast("long")) / 3600,
        )
        .filter(F.col("hours_from_news") <= NEWS_WINDOW_HOURS)
        .groupBy("page_id", "ts", "views", "avg_views")
        .agg(F.min("hours_from_news").alias("hours_from_nearest_news"))
    )

    # The span itn_edit_fact can speak to at all: outside it, "no edit
    # within NEWS_WINDOW_HOURS" says something about the dump's coverage,
    # not about the news. Both bounds are null when itn is empty, so every
    # comparison below is null and every spike falls through to UNKNOWN --
    # which is the honest answer when no ITN page is configured.
    bounds = itn_ts.agg(
        F.min("news_ts").alias("news_from"), F.max("news_ts").alias("news_to")
    )
    window = F.expr(f"interval {NEWS_WINDOW_HOURS} hours")

    result = (
        spikes.join(nearest_news, ["page_id", "ts", "views", "avg_views"], "left")
        .crossJoin(bounds)  # one row, so this is a broadcast, not a blowup
        .withColumn(
            "news_match",
            F.when(F.col("hours_from_nearest_news").isNotNull(), F.lit(NEWS_MATCHED))
            .when(
                F.col("ts").between(
                    F.col("news_from") - window, F.col("news_to") + window
                ),
                F.lit(NEWS_ABSENT),
            )
            .otherwise(F.lit(NEWS_UNKNOWN)),
        )
        .drop("news_from", "news_to")
        .orderBy(F.desc("views"))
        .limit(TOP_N_SPIKES)
    )
    # Name the articles last: after limit() this is a 20-row join, and
    # page_dim's title is the canonical one the fold aggregated onto.
    return result.join(page_dim.select("page_id", "page_title"), "page_id").select(
        "page_title", "ts", "views", "avg_views",
        "hours_from_nearest_news", "news_match",
    ).orderBy(F.desc("views"))
