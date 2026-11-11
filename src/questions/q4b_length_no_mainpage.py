"""
Q4b: article length / revision count vs. pageviews, **excluding the front
page**.

Same aggregation as q4_length_revisions (whose `aggregate()` this calls),
over a page_dim/redirect_dim with `Main_Page` removed from both sides
(questions/pages.py::without_titles).

Q4 averages views over *every* article in a length bucket, which is the
design that made the length effect visible at all (see q4's docstring). The
cost of that denominator is that one freak article moves a bucket's mean:
`Main_Page` drew 32,139,712 views on the enwiki week 2026-09-14..20, so
depending on which bucket its length puts it in, it contributes on the
order of 10 views to that bucket's mean of 22.8 -- a single page worth
~45% of the average, pulling in whichever direction its own length happens
to sit.

That is a different failure from the usual outlier worry: the front page is
not a long-tail article that got lucky, it is the site's navigation, and
its views say nothing about whether length predicts readership. Comparing
q4 with q4b shows how much of the length effect is the measurement and how
much is one row.
"""
from pyspark.sql import DataFrame

from questions.pages import MAIN_PAGE_TITLES, without_titles

from . import q4_length_revisions

LENGTH_BUCKETS = q4_length_revisions.LENGTH_BUCKETS


def required_tables() -> list[str]:
    return ["pageviews_fact", "page_dim", "revision_dim", "redirect_dim"]


def chart_encoding() -> dict:
    encoding = q4_length_revisions.chart_encoding()
    encoding["y"] = dict(encoding["y"], title="Avg views per article (excl. Main_Page)")
    return encoding


def default_mark() -> str:
    # q4's default, deliberately not config.yaml's `line` override: a line
    # across four ordinal buckets draws slope between categories that have
    # no intermediate values.
    return "bar"


def run(tables: dict[str, DataFrame]) -> DataFrame:
    page_dim, redirect_dim = without_titles(
        tables["page_dim"], tables["redirect_dim"], MAIN_PAGE_TITLES
    )
    return q4_length_revisions.aggregate(
        tables["pageviews_fact"], page_dim, tables["revision_dim"], redirect_dim
    )
