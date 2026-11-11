"""Centralized logging setup. Call `configure()` once, from run.py's entry
point; every other module just does `log = logging.getLogger(__name__)`.
"""
import logging
import os


def configure() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
