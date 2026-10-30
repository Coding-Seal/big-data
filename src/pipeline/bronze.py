"""Bronze stage: fetch raw Wikimedia files, unparsed, as published."""
import logging

from config import Config
from sources import mediawiki_history, page_dump, pageviews

from .storage import bronze_dir

log = logging.getLogger(__name__)


def download(config: Config) -> None:
    bronze = bronze_dir(config)

    pageview_dir = bronze / "pageviews"
    fetched = pageviews.download(
        config.date_range.start, config.date_range.end, pageview_dir
    )
    log.info("pageviews: %d hourly file(s) in %s", len(fetched), pageview_dir)

    dump_dir = bronze / config.page_dump.wiki_db
    dumps = page_dump.download(config.page_dump.wiki_db, dump_dir)
    log.info("page_dump: %d file(s) in %s", len(dumps), dump_dir)

    history_dir = bronze / "mediawiki_history" / config.page_dump.wiki_db
    history = mediawiki_history.download(
        config.page_dump.wiki_db,
        history_dir,
        config.date_range.start,
        config.date_range.end,
    )
    log.info("mediawiki_history: %d file(s) in %s", len(history), history_dir)
