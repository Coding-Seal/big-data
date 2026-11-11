"""
Q5: weekday vs. weekend traffic pattern, by hour of day.

A groupBy over pageviews_fact, but resolved onto articles first
(questions/pages.py), for two reasons:

  - `articles` has to be a count of articles. Counting distinct page_title
    counts a redirect as its own article, so the column read high by
    however many alias URLs readers happened to use that hour.
  - `views` is then article traffic, not all traffic. with_page_id drops
    titles that resolve to no namespace-0 page -- `Main_Page`, `Special:*`,
    and pages newer than the dump snapshot -- and those have their own
    weekly rhythm (automated and navigational traffic does not take
    weekends off the way reading does). Mixing them into a weekday/weekend
    comparison confounds exactly the effect being measured. The totals are
    therefore lower than the raw dumps', on purpose, and comparable with
    q1/q4 which already count this way.
"""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from questions.pages import with_page_id

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def required_tables() -> list[str]:
    return ["pageviews_fact", "page_dim", "redirect_dim"]


def chart_encoding() -> dict:
    return {
        "x": {"field": "hour", "type": "ordinal", "title": "Hour (UTC)"},
        "y": {"field": "views", "type": "quantitative"},
        "color": {"field": "day_of_week", "type": "nominal", "sort": DAY_ORDER},
        "tooltip": [
            {"field": "day_of_week"}, {"field": "hour"},
            {"field": "views"}, {"field": "articles"}, {"field": "is_weekend"},
        ],
    }


def default_mark() -> str:
    return "line"


def run(tables: dict[str, DataFrame]) -> DataFrame:
    return aggregate(
        tables["pageviews_fact"], tables["page_dim"], tables["redirect_dim"]
    )


def aggregate(
    pageviews: DataFrame, page_dim: DataFrame, redirect_dim: DataFrame
) -> DataFrame:
    """Shared with q5b_weekday_no_mainpage, which passes a narrowed
    page_dim/redirect_dim rather than reimplementing any of this."""
    articles = with_page_id(pageviews, page_dim, redirect_dim)
    with_date = articles.withColumn("calendar_date", F.to_date("date", "yyyyMMdd"))
    with_dow = with_date.withColumn(
        "day_of_week", F.date_format("calendar_date", "EEEE")
    ).withColumn(
        # Spark's dayofweek(): 1 = Sunday, 7 = Saturday.
        "is_weekend", F.dayofweek("calendar_date").isin([1, 7])
    )

    return (
        with_dow.groupBy("day_of_week", "is_weekend", "hour")
        .agg(
            F.sum("views").alias("views"),
            F.countDistinct("page_id").alias("articles"),
        )
        .orderBy("is_weekend", "day_of_week", "hour")
    )
