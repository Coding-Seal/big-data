---
name: running-pipeline-jobs
description: Use when launching, monitoring, resuming, or diagnosing a Spark run in this project (download / build-silver / build-gold / run-question) — especially on the enwiki profile, where runs take tens of minutes and every failure mode is quiet.
---

# Running the pipeline

The `simple` profile finishes fast enough to run in the foreground and
re-run on a whim. The `enwiki` profile does not: stages take 20–85 minutes
each, and *every* way they go wrong looks like either success or a hang.
Treat an enwiki run as a job you launch and verify, not a command you wait
on.

## Launching

```sh
SPARK_DRIVER_MEMORY=6g setsid nohup devenv shell -- uv run python3 \
  src/run.py --config config.enwiki.yaml build-gold > gold.log 2>&1 < /dev/null &
```

Three parts of that are load-bearing:

- **`SPARK_DRIVER_MEMORY=6g`** for enwiki. `local[*]` runs executors inside
  the driver JVM, and the heap is fixed when the JVM launches — before
  `SparkSession.builder.config()` is read — so setting it in code silently
  does nothing (`common/spark.py`). The `simple` profile is fine on the 1g
  default.
- **`setsid nohup ... &`** with the log redirected. A plain backgrounded
  shell command gets reaped by session cleanup; on 2026-10-27 that killed a
  `build-gold` 40 minutes in, along with every waiter watching it, well
  short of its timeout. `setsid` puts the JVM in its own session so neither
  the shell nor a dying poller can take it down.
- **Redirect to a file, don't pipe.** Piping through `tail`/`grep` buffers
  everything until the process exits, so you get no progress at all. Poll
  the file instead: `until ! pgrep -f <pattern>; do sleep 30; done`.

**Run one Spark session at a time.** The box is ~15GB and an enwiki job
holds ~6GB resident; a second session pushes the machine into swap and
slows both. If you need a quick count while a big job runs, wait.

## Resuming a partial run

`cmd_build_silver` runs three stages in a fixed order, and a kill leaves
the earlier ones committed:

1. `pageviews_fact`
2. `page_dim`, `category_dim`, `redirect_dim` (from the page dump)
3. `revision_dim`, `itn_edit_fact` (from mediawiki_history)

So identify the first stale table and re-run **only** that stage rather
than paying for the whole command again — a scratchpad script mirroring the
relevant lines of `cmd_build_silver` is the cheap way (that is how the
2026-10-27 recovery was done: ~20 min instead of ~40). Check which stage
died by table, not by mtime; mtimes from a killed run look like a
successful one.

Correctness gates for enwiki before trusting a rebuild — all measured, not
guessed. **Every row count here is only valid for one bronze snapshot**, so
record the dump generation next to it: the counts below are the
`Dump completed on 2026-10-08` generation (read it with
`zcat <table>.sql.gz | tail -3`). A mismatch is a stale gate at least as
often as it is a regression — the first three were previously recorded
without a generation, and a 2026-10-28 rebuild of unchanged parser code
then "failed" two of them purely because they had been measured against
earlier bronze.

| table | expected (bronze 2026-10-08) |
| --- | --- |
| `page_dim` | 7,249,474 (7,140,548 means the split-parser bug is back) |
| `redirect_dim` | 12,038,184 |
| `category_dim` | 209,368,878 |
| `hidden_category_dim` | 92,852 |
| `revision_dim` | 1,622,229 (8,689 means only the `2026-10` stub parsed) |
| `itn_edit_fact` | non-zero — 136 for a September window (0 means the namespace split broke) |
| `pageviews_fact` | 7 dates × 24 hours, one part file each |

Before concluding a mismatch is a bug, rule out the cheap explanations in
this order: is the diff to the parser actually non-additive
(`git diff -U0 -- <file> | grep -E "^-[^-]"`); do all the dumps report the
same `Dump completed on` date (`download` **skips files already present**,
so a bronze directory can legitimately hold mixed generations); and is any
decompressed `.sql` a faithful copy of its `.gz` (`dump_path` silently
prefers `.sql` — compare `grep -c "^("` on both).

Counting rows needs the venv: `devenv shell -- uv run python3` then
`spark.read.parquet('data/silver/en/<table>').count()`. `uv` is not on
`PATH` in a bare shell and `pyarrow` is not a dependency, so neither bare
`uv run` nor a pyarrow footer read works.

## Reading a failure

- **A `RejectedExecutionException` cascade** from
  `ThreadPoolExecutor[Terminated/Shutting down]`, with **no** Python
  traceback and no `OutOfMemoryError`, is shutdown noise from an external
  kill — not an application bug. Don't go hunting for a data problem.
- **A missing `_SUCCESS` is not a failed write** when the table is
  partitioned: `partitionOverwriteMode=dynamic` can leave it off. Verify by
  counting partitions (and by whether later stages committed — they
  couldn't have if the write had died).
- **Slow is not hung.** Before concluding either, measure: stage progress
  in the log, `%CPU` and RSS from `ps`, spill size in `/tmp/blockmgr-*`,
  and `free -m`. Two real cases: `devenv shell` once spent ~2h provisioning
  before Spark even started (first log timestamp, not launch time, tells
  you when the job began); and `spark.sql.shuffle.partitions` at `8` made
  enwiki's Q1 spill 24GB and thrash with repeated
  `RowBasedKeyValueBatch: Calling spill() ... Will not spill but return 0`.
- **Shuffle sizing is a ceiling, not a target.** AQE only coalesces
  partitions *downward*, so a low `shuffle.partitions` cannot be raised
  back up when the data turns out to be large. See the comment on
  `SHUFFLE_PARTITIONS` in `common/spark.py` for the measured before/after.

## After a run finishes

Don't report numbers straight out of a completed run — a run that exits 0
can still have answered over the wrong data. Go through
`.agents/skills/validating-question-output` first.
