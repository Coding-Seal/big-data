"""Category aggregation, and telling tracking tags from subject categories.

MediaWiki categories are two different things wearing one name: a handful
describe what an article is *about*, and tens of thousands exist to drive
maintenance workflows and template bookkeeping. At enwiki scale the second
kind completely dominates by traffic -- measured on the 2026-09-14..20
window, all 15 of the top categories by views are tracking tags, led by
`Articles_with_short_description` (454M views across 2.81M articles).

So a "traffic by category" answer is really two answers, and this module
exists so both can be asked of the same aggregation (see q1_topic_time and
q1b_topic_time_filtered).

**The test is structural, not textual.** MediaWiki marks a tracking
category by setting `__HIDDENCAT__` on the category page, and the dumps
expose it in `page_props.sql.gz`; `sources/page_dump.py` turns that into
`hidden_category_dim`, which this module anti-joins. An earlier version
matched category *names* against enwiki's tracking-tag conventions
instead, and the measurements are why it is gone: round one left 6 of the
filtered top 15 still tracking tags, and closing those six surfaced 3 more
from the next tier (`Certification_Table_Entry_usages_for_United_Kingdom`,
`IBDB_name_template_using_Wikidata`, ...) at ~21 minutes per round. Hidden
categories share a flag, not a naming convention, so no pattern list
converges.

One deliberate behaviour change from that switch: categories MediaWiki does
*not* hide are now kept even when they are administrative in spirit --
`Living_people` (80.9M views on the enwiki window) is a real, visible
category, so the structural test keeps it where the old regex dropped it by
editorial judgement. That is the more defensible answer, but it is a change
in what the chart shows.

**What survives still isn't a topic taxonomy.** MediaWiki categories are
far narrower than topics, and overlapping: with tracking tags gone, the
enwiki top 15 was 9 American screen-actor categories sliced by medium,
gender and century -- one readership phenomenon drawn as 9 series. The
`topic_dim` in tasks.md is the gap that closes that; this module only
removes bookkeeping.
"""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from questions.pages import with_page_id

def views_by_category_hour(
    views: DataFrame,
    page_dim: DataFrame,
    category_dim: DataFrame,
    redirect_dim: DataFrame,
    top_n: int,
    drop_hidden: bool,
    hidden_category_dim: DataFrame | None = None,
) -> DataFrame:
    """Views and article counts per (category, hour), capped to the top
    `top_n` categories by total views.

    `views` folds through `with_page_id` first, so redirect traffic lands on
    the article it points at and `articles` counts articles rather than URL
    titles (questions/pages.py).

    Note the view counts are **not** additive across categories: an article
    belongs to many at once, so one view is counted once per category it
    carries. On the measured window the top 15 categories sum to ~1.89B
    against 501.9M of actual article traffic. Any chart over this must
    therefore disable stacking -- a stacked total is meaningless here.
    """
    categories = category_dim
    if drop_hidden:
        if hidden_category_dim is None:
            raise ValueError("drop_hidden=True needs hidden_category_dim")
        # Anti-join on the name, because that is what category_dim carries;
        # hidden_category_dim is keyed the same way (see
        # sources/page_dump.py). Kept before the pageviews join so the
        # tracking categories -- which are the most widely applied ones --
        # never enter the ~25x fan-out below.
        categories = categories.join(
            hidden_category_dim.select("category").distinct(), "category", "left_anti"
        )

    # Collapse to one row per (page_id, hour) *before* the category join.
    # pageviews_fact is keyed (title, date, hour) and this question sums
    # across dates, so a page viewed all week arrives as up to 7 rows per
    # hour-of-day -- and category_dim fans every one of them out ~25x
    # (183.8M category rows / 7.25M articles). Summing the dates first is
    # identical arithmetic: sum(views) becomes a sum of sums, and the
    # page_id set behind each (category, hour) is untouched, so `articles`
    # is unchanged too (verified by exceptAll both ways, and the enwiki
    # numbers are unchanged).
    #
    # Worth less than the row arithmetic suggests: **measured 29m40s ->
    # 25m18s on enwiki, ~15%**, not the 7x the fan-out implies. 7x is the
    # ceiling, hit only by pages viewed in the same hour on all seven days;
    # the long tail appears in a handful of hours all week and barely
    # collapses, and this buys its reduction with an extra shuffle. Q1 is
    # still the most expensive question by far -- the remaining cost is the
    # countDistinct over ~2M category groups and the unavoidable shuffle of
    # all 183.8M category rows, not the fan-out.
    per_page_hour = (
        with_page_id(views, page_dim, redirect_dim)
        .groupBy("page_id", "hour")
        .agg(F.sum("views").alias("views"))
    )

    # The `merge` hint is load-bearing, not tuning. Pre-aggregating shrinks
    # Spark's size estimate for the left side enough that the optimizer
    # switches to a broadcast hash join, then under-predicts the real
    # materialized size and dies in BroadcastExchangeExec -- "Not enough
    # memory to build and broadcast the table", measured on the *simple*
    # profile at the 1g default heap. Neither side is ever broadcast-sized
    # in practice (183.8M category rows against millions of page-hours), so
    # pin sort-merge instead of relying on an estimate this aggregation
    # perturbs.
    agg = (
        per_page_hour.hint("merge")
        .join(categories, "page_id")
        .groupBy("category", "hour")
        .agg(
            F.sum("views").alias("views"),
            F.countDistinct("page_id").alias("articles"),
        )
    )

    top = (
        agg.groupBy("category")
        .agg(F.sum("views").alias("total_views"))
        .orderBy(F.desc("total_views"))
        .limit(top_n)
        .select("category")
    )
    return agg.join(top, "category").orderBy(F.desc("views"))
