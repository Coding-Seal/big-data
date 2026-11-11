---
name: running-pipeline-jobs
description: Use when launching, monitoring, resuming, or diagnosing a Spark run in this project (download / build-silver / build-gold / run-question) — especially on the enwiki profile, where runs take tens of minutes and every failure mode is quiet.
---

# Running the pipeline

The `simple` profile finishes fast enough to run in the foreground and re-run on a whim. The `enwiki` profile does not: stages take 20–85 minutes each, and *every* way they go wrong looks like either success or a hang. Treat an enwiki run as a job you launch and verify, not a command you wait on.

## Launching

**In a container (recommended):** the container runtime supervises the process itself, independent of the shell that launched it, so `-d` alone is enough — no `setsid`/`nohup` needed (verified 2026-11-11: a `podman run -d` enwiki job survived its launching shell exiting, with no detach trick at all).

```sh
docker run -d --name big-data-enwiki -e SPARK_DRIVER_MEMORY=6g \
  -v "$(pwd)/data:/app/data" big-data config=config.enwiki.yaml build-gold
docker logs -f big-data-enwiki      # follow progress
docker wait big-data-enwiki         # blocks until it exits, prints the exit code
```
(substitute `podman` for `docker` if that's the engine on `PATH` — identical flags.)

**Plain `uv`, no container:**

```sh
mkdir -p logs && SPARK_DRIVER_MEMORY=6g setsid nohup uv run python3 \
  src/run.py --config config.enwiki.yaml build-gold > logs/gold.log 2>&1 < /dev/null &
```

Three parts of that are load-bearing here specifically because there's no container runtime managing the process:

- **`SPARK_DRIVER_MEMORY=6g`** for enwiki. `local[*]` fixes the driver heap at JVM launch, before `SparkSession.builder.config()` is read, so setting it in code does nothing (`pipeline/spark.py`). The `simple` profile is fine on the 1g default.
- **`setsid nohup ... &`** with the log redirected. A plain backgrounded shell command gets reaped by session cleanup — on 2026-10-27 that killed a `build-gold` 40 minutes in, well short of its timeout. `setsid` puts the JVM in its own session so neither the shell nor a dying poller can take it down.
- **Redirect to a file, don't pipe.** Piping through `tail`/`grep` buffers everything until the process exits, so you get no progress at all. Poll instead: `until ! pgrep -f <pattern>; do sleep 30; done`.

**Run one Spark session at a time**, container or not. The box is ~15GB and an enwiki job holds ~6GB resident; a second session pushes the machine into swap and slows both. If you need a quick count while a big job runs, wait.

## Resuming a partial run

`cmd_build_silver` runs three stages in a fixed order, and a kill leaves the earlier ones committed:

1. `pageviews_fact`
2. `page_dim`, `category_dim`, `redirect_dim` (from the page dump)
3. `revision_dim`, `itn_edit_fact` (from mediawiki_history)

Identify the first stale table and re-run **only** that stage rather than paying for the whole command again — a scratchpad script mirroring the relevant lines of `cmd_build_silver` is the cheap way (2026-10-27 recovery: ~20 min instead of ~40). Check which stage died by table, not by mtime; mtimes from a killed run look like a successful one.

Correctness gates for enwiki before trusting a rebuild, all measured, not guessed. **Every row count here is only valid for one bronze snapshot**, so record the dump generation next to it — the counts below are the `Dump completed on 2026-10-08` generation (read it with `zcat <table>.sql.gz | tail -3`). A mismatch is a stale gate at least as often as a regression: a 2026-10-28 rebuild of unchanged parser code "failed" two of these purely because they'd been recorded against earlier bronze.

| table | expected (bronze 2026-10-08) |
| --- | --- |
| `page_dim` | 7,249,474 (7,140,548 means the split-parser bug is back) |
| `redirect_dim` | 12,038,184 |
| `category_dim` | 209,368,878 |
| `hidden_category_dim` | 92,852 |
| `revision_dim` | 1,622,229 (8,689 means only the `2026-10` stub parsed) |
| `itn_edit_fact` | non-zero — 136 for a September window (0 means the namespace split broke) |
| `pageviews_fact` | 7 dates × 24 hours, one part file each |

Before concluding a mismatch is a bug, rule out the cheap explanations in this order: is the diff to the parser actually non-additive (`git diff -U0 -- <file> | grep -E "^-[^-]"`); do all the dumps report the same `Dump completed on` date (`download` **skips files already present**, so a bronze directory can legitimately hold mixed generations); and is any decompressed `.sql` a faithful copy of its `.gz` (`dump_path` silently prefers `.sql` — compare `grep -c "^("` on both).

Counting rows needs the venv: `uv run python3` (or, for a container run, `docker exec big-data-enwiki uv run python3`) then `spark.read.parquet('data/silver/en/<table>').count()`. `pyarrow` is not a dependency, so a bare pyarrow footer read doesn't work either — it has to go through Spark.

## Reading a failure

- **A `RejectedExecutionException` cascade** from `ThreadPoolExecutor[Terminated/Shutting down]`, with **no** Python traceback and no `OutOfMemoryError`, is shutdown noise from an external kill — not an application bug. Don't go hunting for a data problem.
- **A missing `_SUCCESS` is not a failed write** when the table is partitioned: `partitionOverwriteMode=dynamic` can leave it off. Verify by counting partitions (and by whether later stages committed — they couldn't have if the write had died).
- **Slow is not hung.** Before concluding either, measure: stage progress in the log, `%CPU`/RSS from `ps`, spill size in `/tmp/blockmgr-*`, and `free -m`. Real case: `shuffle.partitions=8` made enwiki's Q1 spill 24GB and thrash with repeated `RowBasedKeyValueBatch: ... Will not spill but return 0`. The first log timestamp, not launch time, tells you when the job actually began — a slow image pull or `uv sync` beforehand isn't the job hanging.
- **Shuffle sizing is a ceiling, not a target.** AQE only coalesces partitions *downward*, so a low `shuffle.partitions` cannot be raised back up when the data turns out to be large. See the comment on `SHUFFLE_PARTITIONS` in `pipeline/spark.py` for the measured before/after.

## After a run finishes

Don't report numbers straight out of a completed run — a run that exits 0 can still have answered over the wrong data. Go through `.agents/skills/validating-question-output` first.
