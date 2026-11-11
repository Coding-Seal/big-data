"""Resolving the titles readers actually requested onto `page_dim.page_id`.

`pageviews_fact` keys on the title in the URL; `page_dim` holds only
canonical namespace-0, non-redirect pages. Joining the two on `page_title`
directly throws away every view that landed on a redirect -- measured at
806 titles / 1,026 views (7.2% of all traffic) on the 2026-10-04 simplewiki
slice, and concentrated on exactly the news-driven pages (`Solar_system`,
`Nobel_prize`, `Israel-Hamas_war`) the questions care most about.

This is the one place that knows how to bridge the two, so question modules
don't each reimplement it (and each get it subtly differently).
"""
from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

# MediaWiki caps page titles at 255 bytes, so this is "the rest of the
# string" for any real title.
_MAX_TITLE_LEN = 255

# The front page is a namespace-0 non-redirect, so it sits in page_dim and
# counts as an article in every question unless excluded on purpose. Both
# configured profiles spell it the same way; a wiki that doesn't would need
# this in config.yaml alongside mediawiki_history.itn_page_title.
MAIN_PAGE_TITLES = ["Main_Page"]


def normalize_title(title: Column) -> Column:
    """Upper-case the first character, leave the rest alone.

    MediaWiki does this to every title ($wgCapitalLinks, on by default), so
    `main_page` and `Main_page` are both requests for `Main_page` and show
    up as distinct rows in the pageviews dumps. The rest of a title *is*
    case-sensitive -- `initcap()` would be wrong here, it would rewrite
    `Apple_Inc.` to `Apple_inc.`.
    """
    return F.concat(
        F.upper(F.substring(title, 1, 1)), F.substring(title, 2, _MAX_TITLE_LEN)
    )


def without_titles(
    page_dim: DataFrame, redirect_dim: DataFrame, titles: list[str]
) -> tuple[DataFrame, DataFrame]:
    """`(page_dim, redirect_dim)` with `titles`' articles removed from both.

    Both sides, because `with_page_id` resolves a view through either one:
    dropping a title from `page_dim` alone leaves every redirect pointing at
    it still mapping onto its `page_id`, so the traffic survives attributed
    to an article that is no longer in the dimension -- 26 of `Main_Page`'s
    32.1M views arrive under variants like `HomePage` and `Mainpage`, so
    that half is not a rounding error.

    Pass canonical titles; redirects to them are handled by the `page_id`
    join rather than by name.
    """
    excluded = page_dim.filter(F.col("page_title").isin(titles)).select("page_id")
    return (
        page_dim.join(excluded, "page_id", "left_anti"),
        redirect_dim.join(
            excluded.withColumnRenamed("page_id", "to_page_id"),
            "to_page_id",
            "left_anti",
        ),
    )


def with_page_id(
    views: DataFrame, page_dim: DataFrame, redirect_dim: DataFrame
) -> DataFrame:
    """`views` (any frame with a `page_title`) plus a `page_id` column, with
    redirect titles mapped onto the article they point at.

    Rows whose title matches neither a canonical page nor a redirect are
    dropped: those are pages created after the dump snapshot was taken (the
    dumps and the pageviews files are not from the same instant), and there
    is nothing in `page_dim` to attribute them to.

    Note the caller must aggregate by `page_id`, not `page_title`, after
    this -- several titles legitimately resolve to the same article.
    """
    # page_dim is is_redirect=0 and redirect_dim's from_title is is_redirect=1,
    # both namespace 0, and MediaWiki enforces (namespace, title) uniqueness --
    # so the two sides are disjoint and this union can't double-count a view.
    canonical = page_dim.select(F.col("page_title").alias("_title"), "page_id")
    via_redirect = redirect_dim.select(
        F.col("from_title").alias("_title"), F.col("to_page_id").alias("page_id")
    )
    titles = canonical.unionByName(via_redirect)

    return (
        views.withColumn("_title", normalize_title(F.col("page_title")))
        .join(titles, "_title")
        .drop("_title")
    )
