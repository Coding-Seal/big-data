"""
Q1b: traffic distribution by category x time of day, **excluding**
maintenance and template-bookkeeping categories.

Same aggregation as q1_topic_time (common/categories.py), one filter
different. The pair is the point: q1 shows that MediaWiki categories are
dominated by tracking tags, q1b shows what is left once they are gone, and
reporting only one of the two would be the misleading half.

"Maintenance" here means MediaWiki's own `__HIDDENCAT__` flag, read from
`page_props.sql.gz` into `hidden_category_dim` -- not a guess from the
category's name. That distinction is load-bearing: the name-pattern version
this replaced leaked tracking tags into the top 15 twice over.

What this is not: a topic taxonomy. What survives is still raw categories,
typically far narrower than a topic (`1980s_American_television_sitcoms`,
not `Television`) and freely overlapping, so the top-N tends to be several
slices of one subject. Read it as "the most-viewed non-tracking
categories", with the caveat that `category_dim` carries no notion of topic
at all.
"""
from pyspark.sql import DataFrame

from common.categories import views_by_category_hour

# Same cap and reasoning as q1_topic_time's.
TOP_N_CATEGORIES = 15


def required_tables() -> list[str]:
    return [
        "pageviews_fact", "page_dim", "category_dim", "redirect_dim",
        "hidden_category_dim",
    ]


def chart_encoding() -> dict:
    return {
        "x": {"field": "hour", "type": "ordinal", "title": "Hour (UTC)"},
        "y": {
            "field": "views",
            "type": "quantitative",
            # Non-exclusive series: see q1_topic_time.chart_encoding().
            "stack": None,
        },
        "color": {"field": "category", "type": "nominal", "title": "Category (non-maintenance)"},
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
        drop_hidden=True,
        hidden_category_dim=tables["hidden_category_dim"],
    )
