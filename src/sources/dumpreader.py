"""Reading Wikimedia's MySQL dumps with Spark.

Tuple-level parsing lives in `sqldump.py`, which is shipped to executors;
this module is the driver-side half -- locating a dump, checking it holds
the table expected, and turning its INSERT lines into an RDD of rows.

The parsing is shape-based and streamed line-by-line; both choices fixed
real bugs, recorded in AGENTS.md and docs/sources/page-dump.md.
"""
import gzip
from pathlib import Path

# Shipped via addPyFile and imported by plain name on executors, so the
# module name has to match on both sides without zipping `sources/`.
SQLDUMP_PATH = Path(__file__).resolve().parent / "sqldump.py"


def dump_path(bronze_dir: Path, table: str) -> Path:
    """`<table>.sql` if someone has decompressed it, else `<table>.sql.gz`.

    gzip has no sync points, so Spark parses a `.gz` on a single core --
    22 minutes for enwiki's 2.43GB page dump with seven cores idle. Plain
    text is splittable, so `gunzip -k` first (expands ~6x) to use them all.
    """
    plain = bronze_dir / f"{table}.sql"
    return plain if plain.exists() else bronze_dir / f"{table}.sql.gz"


def assert_single_table(path: Path, table_name: str) -> None:
    """One table per file is what lets `parse_table` identify data lines by
    shape alone, so it is worth reading the DDL header to confirm."""
    marker = f"INSERT INTO `{table_name}`"
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("INSERT INTO `"):
                if not line.startswith(marker):
                    raise ValueError(
                        f"{path} contains {line[:40]!r}, expected {marker!r}"
                    )
                return
    raise ValueError(f"no INSERT statement found in {path}")


def parse_table(sc, path: Path, table_name: str, row_fn):
    """RDD of `row_fn(fields)` over every INSERT tuple in `path`."""
    import sqldump  # shipped via addPyFile by the caller

    assert_single_table(path, table_name)

    def parse_partition(lines):
        for line in lines:
            # Data lines are recognised by shape, not by position after an
            # INSERT: a split dump starts mid-statement, and tracking
            # "inside the block" instead silently dropped 109K pages.
            if line.startswith("("):
                yield from (row_fn(f) for f in sqldump.parse_insert_line(line))

    # Line-by-line: wholeTextFiles overflowed the driver heap on a 30MB dump.
    return sc.textFile(str(path)).mapPartitions(parse_partition)
