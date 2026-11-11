"""
Q5b: weekday vs. weekend traffic, **excluding the front page**.

Same aggregation as q5_weekday (whose `aggregate()` this calls), over a
page_dim/redirect_dim with `Main_Page` removed from both sides
(questions/pages.py::without_titles).

Why this variant exists rather than just a caveat on q5: the front page is
a namespace-0 non-redirect, so the fold keeps it, and on the enwiki week
2026-09-14..20 it is the single largest article at 32,139,712 views --
6.4% of all article traffic, arriving under 26 title variants. Q5 asks
whether *reading* slows at the weekend; traffic that lands on the front
page is navigational and partly automated, and there is no reason to think
it shares the weekly rhythm of article reading. Leaving it in puts 6.4% of
a different behaviour inside the effect being measured.

Which of the two is "right" depends on the claim being made, so both are
published: q5 is all article traffic, q5b is article traffic minus the
front door. Compare the weekend/weekday ratios rather than reading either
alone.
"""
from pyspark.sql import DataFrame

from questions.pages import MAIN_PAGE_TITLES, without_titles

from . import q5_weekday

DAY_ORDER = q5_weekday.DAY_ORDER


def required_tables() -> list[str]:
    return ["pageviews_fact", "page_dim", "redirect_dim"]


def chart_encoding() -> dict:
    encoding = q5_weekday.chart_encoding()
    encoding["y"] = dict(encoding["y"], title="Views (excl. Main_Page)")
    return encoding


def default_mark() -> str:
    return q5_weekday.default_mark()


def run(tables: dict[str, DataFrame]) -> DataFrame:
    page_dim, redirect_dim = without_titles(
        tables["page_dim"], tables["redirect_dim"], MAIN_PAGE_TITLES
    )
    return q5_weekday.aggregate(tables["pageviews_fact"], page_dim, redirect_dim)
