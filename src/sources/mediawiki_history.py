"""
Mediawiki history source module: revision-level edit log -> `revision_dim`
(Q4's revision-count half) and `itn_edit_fact` (Q2's news-timeline half).
See docs/sources/mediawiki-history.md for the verified 78-column schema and
docs/arch/layered-design.md for the source-module contract.

No "latest" alias exists for this dataset (unlike page_dump's
`{wiki_db}-latest-*`), and only the last two monthly snapshot generations
are retained -- today's names (e.g. "2026-08") will 404 in a few months.
download() discovers the real snapshot and filenames from the dumps site's
own directory listings instead of hardcoding either.
"""
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from sources.http import fetch_text, fetch_to
from sources.namespaces import split_prefixed_title

INDEX_URL = "https://dumps.wikimedia.org/other/mediawiki_history/"
WIKI_DIR_URL_TMPL = INDEX_URL + "{snapshot}/{wiki_db}/"
NUM_FIELDS = 78  # see docs/sources/mediawiki-history.md

_SNAPSHOT_RE = re.compile(r'href="(\d{4}-\d{2})/"')
_FILE_RE = re.compile(r'href="([\w.\-]+\.tsv\.bz2)"')

log = logging.getLogger(__name__)


def describe() -> dict:
    return {
        "name": "mediawiki_history",
        "format": "TSV + bzip2, splittable, 78 positional columns (no header)",
        "partitioning": "one all-time file per small wiki, or one file per "
        "wiki per month for bigger wikis",
    }


def _latest_snapshot() -> str:
    html = fetch_text(INDEX_URL)
    snapshots = sorted(set(_SNAPSHOT_RE.findall(html)))
    if not snapshots:
        raise RuntimeError(f"no snapshot directories found at {INDEX_URL}")
    return snapshots[-1]


def _wiki_files(snapshot: str, wiki_db: str) -> list[str]:
    url = WIKI_DIR_URL_TMPL.format(snapshot=snapshot, wiki_db=wiki_db)
    html = fetch_text(url)
    files = sorted(set(_FILE_RE.findall(html)))
    if not files:
        raise RuntimeError(f"no .tsv.bz2 files found for {wiki_db} at {url}")
    return files


def _covered_months(start: str, end: str) -> set[str]:
    """[start, end] as pageviews-style '%Y-%m-%dT%H' -> the 'YYYY-MM' months
    they span (inclusive)."""
    start_dt = datetime.strptime(start, "%Y-%m-%dT%H")
    end_dt = datetime.strptime(end, "%Y-%m-%dT%H")
    months = set()
    cur = start_dt.replace(day=1)
    end_month = end_dt.replace(day=1)
    while cur <= end_month:
        months.add(cur.strftime("%Y-%m"))
        cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
    return months


def download(
    wiki_db: str, dest: Path, date_range_start: str, date_range_end: str
) -> list[Path]:
    """Fetch the mediawiki_history file(s) for `wiki_db` covering
    [date_range_start, date_range_end] (pageviews-style "%Y-%m-%dT%H").

    Small wikis publish one `<snapshot>.<wiki_db>.all-time.tsv.bz2` file
    (grabbed whole); bigger wikis publish one file per month, in which case
    only the months the date range touches are fetched -- same "no wasted
    bandwidth" reasoning as docs/sources/mediawiki-history.md. Resumable: a
    file already present in `dest` is skipped.
    """
    dest.mkdir(parents=True, exist_ok=True)
    snapshot = _latest_snapshot()
    all_files = _wiki_files(snapshot, wiki_db)

    if len(all_files) == 1 and ".all-time.tsv.bz2" in all_files[0]:
        filenames = all_files
    else:
        months = _covered_months(date_range_start, date_range_end)
        filenames = [f for f in all_files if any(f.endswith(f"{m}.tsv.bz2") for m in months)]
        if not filenames:
            raise RuntimeError(
                f"no mediawiki_history files for {wiki_db} covering {sorted(months)} "
                f"(snapshot {snapshot} has: {all_files})"
            )

    base_url = WIKI_DIR_URL_TMPL.format(snapshot=snapshot, wiki_db=wiki_db)
    paths = []
    for filename in filenames:
        path = dest / filename
        if path.exists():
            log.info("skip (already have) %s", path.name)
        else:
            log.info("fetching %s", path.name)
            fetch_to(base_url + filename, path)
        paths.append(path)
    return paths


def to_silver(
    spark: SparkSession, bronze_dir: Path, wiki: str, itn_page_title: str | None
) -> dict[str, DataFrame]:
    """Returns {"revision_dim": DataFrame, "itn_edit_fact": DataFrame} per
    the silver schema in docs/arch/layered-design.md:
      revision_dim(wiki, page_id, revision_count, first_edit_ts, last_edit_ts)
      itn_edit_fact(wiki, event_timestamp, event_comment, revision_text_bytes_diff)

    `itn_page_title` is the wiki's "In the news" style page (e.g.
    "Wikipedia:In_the_news" on enwiki) -- not every wiki maintains one (the
    project's default `simple` config does not, see
    docs/sources/wikinews-itn.md), so it's optional: None yields an empty
    itn_edit_fact with the right schema rather than failing.
    """
    files = sorted(bronze_dir.glob("*.tsv.bz2"))
    if not files:
        raise FileNotFoundError(f"no bronze mediawiki_history files in {bronze_dir}")

    raw = spark.read.text([str(f) for f in files])
    parts = F.split(F.col("value"), "\t")
    parsed = (
        raw.filter(F.size(parts) == NUM_FIELDS)
        .select(
            parts.getItem(2).alias("event_entity"),
            parts.getItem(4).alias("event_timestamp"),
            parts.getItem(5).alias("event_comment"),
            parts.getItem(28).cast("long").alias("page_id"),
            parts.getItem(30).alias("page_title"),
            parts.getItem(33).cast("int").alias("page_namespace"),
            parts.getItem(39).cast("long").alias("page_revision_count"),
            parts.getItem(66).cast("long").alias("revision_text_bytes_diff"),
        )
        .filter(F.col("event_entity") == "revision")
    )

    revision_dim = (
        parsed.filter(F.col("page_namespace") == 0)
        .groupBy("page_id")
        .agg(
            F.max("page_revision_count").alias("revision_count"),
            F.min("event_timestamp").alias("first_edit_ts"),
            F.max("event_timestamp").alias("last_edit_ts"),
        )
        .withColumn("wiki", F.lit(wiki))
    )

    if itn_page_title:
        # (namespace, title), not a prefixed string: this dataset keeps the
        # namespace in its own column, so filtering page_title ==
        # "Wikipedia:In_the_news" silently matched zero rows. The real page
        # is page_title == "In_the_news" with page_namespace == 4.
        itn_namespace, itn_title = split_prefixed_title(itn_page_title)
        itn_edit_fact = (
            parsed.filter(
                (F.col("page_namespace") == itn_namespace)
                & (F.col("page_title") == itn_title)
            )
            .select("event_timestamp", "event_comment", "revision_text_bytes_diff")
            .withColumn("wiki", F.lit(wiki))
        )
    else:
        log.warning(
            "mediawiki_history: no itn_page_title configured -- itn_edit_fact will be empty "
            "(see docs/sources/wikinews-itn.md)"
        )
        itn_edit_fact = spark.createDataFrame(
            [],
            "wiki string, event_timestamp string, event_comment string, "
            "revision_text_bytes_diff long",
        )

    log.info("mediawiki_history: parsed revision_dim and itn_edit_fact from %s", bronze_dir)
    return {"revision_dim": revision_dim, "itn_edit_fact": itn_edit_fact}
