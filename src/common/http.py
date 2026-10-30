"""Shared download helper for source modules.

Retries on transient network/SSL errors -- hit a real
`ssl.SSLEOFError: UNEXPECTED_EOF_WHILE_READING` against dumps.wikimedia.org
while building this pipeline; an immediate retry succeeded, confirming it
was a transient connection drop, not a systemic cert/SSL config problem.
"""
import logging
import os
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "big-data-coursework-pipeline/0.1 (polytech big-data course project)"
# dumps.wikimedia.org 403s requests with no / generic User-Agent -- see
# https://meta.wikimedia.org/wiki/User-Agent_policy

RETRIES = 3
RETRY_DELAY_S = 2

log = logging.getLogger(__name__)


def fetch_to(url: str, dest: Path) -> None:
    """Download `url` to `dest`, atomically (via a .part temp file) and with
    retries on transient errors. Raises on a real HTTP error (e.g. 404) or
    after exhausting retries.
    """
    # PID-scoped temp name, not a plain ".part": two config profiles share
    # one bronze/pageviews directory (pipeline/storage.py), so two
    # downloads can legitimately race for the same destination. With a
    # fixed name they clobber each other's temp file and the loser dies on
    # rename with a confusing FileNotFoundError. Worst case now is the same
    # bytes fetched twice.
    tmp = dest.with_suffix(f"{dest.suffix}.{os.getpid()}.part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
                # Streamed, not resp.read(): these range from 54MB hourly
                # pageviews files to enwiki's 2.54GB categorylinks dump,
                # and buffering one of the latter in the driver's heap
                # while Spark is also running is how you OOM a laptop.
                shutil.copyfileobj(resp, f, length=1024 * 1024)
            tmp.rename(dest)  # atomic: a failed download never looks "already have"
            return
        except urllib.error.HTTPError:
            tmp.unlink(missing_ok=True)
            raise  # real HTTP error (404, 403, ...) -- retrying won't help
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            tmp.unlink(missing_ok=True)
            if attempt < RETRIES:
                log.warning(
                    "transient error fetching %s (attempt %d/%d): %s -- retrying",
                    url, attempt, RETRIES, e,
                )
                time.sleep(RETRY_DELAY_S)
    raise RuntimeError(f"failed to fetch {url} after {RETRIES} attempts: {last_err}") from last_err


def fetch_text(url: str) -> str:
    """GET `url` as text, with the same retry/User-Agent policy as fetch_to.

    Used for directory-listing discovery (e.g. mediawiki_history's snapshot
    directories), not for bronze file downloads.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError:
            raise  # real HTTP error (404, 403, ...) -- retrying won't help
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            if attempt < RETRIES:
                log.warning(
                    "transient error fetching %s (attempt %d/%d): %s -- retrying",
                    url, attempt, RETRIES, e,
                )
                time.sleep(RETRY_DELAY_S)
    raise RuntimeError(f"failed to fetch {url} after {RETRIES} attempts: {last_err}") from last_err
