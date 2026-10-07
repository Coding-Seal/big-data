"""
CLI entrypoint: download bronze data, build silver tables, run a question
module against them, or build gold chart specs. See
docs/arch/layered-design.md for the architecture this implements.

    uv run python3 src/run.py download
    uv run python3 src/run.py build-silver
    uv run python3 src/run.py run-question q1_topic_time
    uv run python3 src/run.py build-gold

(or just `just download` / `just build-silver` / `just question <name>` /
`just gold`)
"""
import argparse
import json
import logging
from pathlib import Path

from common.charts import to_vega_lite
from common.logging import configure
from common.spark import get_spark
from config import Config, load_config
from questions import q1_topic_time, q4_length_revisions
from sources import page_dump, pageviews

# config.yaml and data/ live at the repo root, one level up from src/.
REPO_ROOT = Path(__file__).resolve().parent.parent

QUESTIONS = {
    "q1_topic_time": q1_topic_time,
    "q4_length_revisions": q4_length_revisions,
}

log = logging.getLogger(__name__)


def storage_paths(config: Config) -> tuple[Path, Path, Path]:
    root = REPO_ROOT / config.storage_root
    return root / "bronze", root / "silver", root / "gold"


def cmd_download(config: Config) -> None:
    bronze, _, _ = storage_paths(config)
    fetched = pageviews.download(
        config.date_range.start, config.date_range.end, bronze / "pageviews"
    )
    log.info("pageviews: %d hourly file(s) in %s", len(fetched), bronze / "pageviews")

    dump_paths = page_dump.download(
        config.page_dump.wiki_db, bronze / config.page_dump.wiki_db
    )
    log.info(
        "page_dump: %d file(s) in %s", len(dump_paths), bronze / config.page_dump.wiki_db
    )


def cmd_build_silver(config: Config) -> None:
    bronze, silver, _ = storage_paths(config)
    spark = get_spark("build-silver")

    pageviews_fact = pageviews.to_silver(
        spark, bronze / "pageviews", config.wiki, config.pageviews.domain_codes
    )
    pageviews_fact.write.mode("overwrite").partitionBy("date", "hour").parquet(
        str(silver / "pageviews_fact")
    )
    log.info(
        "pageviews_fact: %s rows -> %s",
        f"{pageviews_fact.count():,}", silver / "pageviews_fact",
    )

    dims = page_dump.to_silver(spark, bronze / config.page_dump.wiki_db, config.wiki)
    dims["page_dim"].write.mode("overwrite").parquet(str(silver / "page_dim"))
    dims["category_dim"].write.mode("overwrite").parquet(str(silver / "category_dim"))
    log.info(
        "page_dim: %s rows -> %s", f"{dims['page_dim'].count():,}", silver / "page_dim"
    )
    log.info(
        "category_dim: %s rows -> %s",
        f"{dims['category_dim'].count():,}", silver / "category_dim",
    )

    spark.stop()


def cmd_run_question(config: Config, name: str) -> None:
    _, silver, _ = storage_paths(config)
    spark = get_spark(f"question-{name}")

    module = QUESTIONS[name]
    tables = {
        table: spark.read.parquet(str(silver / table)) for table in module.required_tables()
    }
    module.run(tables).show(20, truncate=False)

    spark.stop()


def cmd_build_gold(config: Config) -> None:
    """Run every question and write its result as a Vega-Lite chart spec --
    data/encoding from the question module, mark type from config.yaml's
    `gold:` section if present (see Config.gold), else the module's own
    default_mark(). Changing a chart's type is a config edit, not a code
    change.
    """
    _, silver, gold = storage_paths(config)
    gold.mkdir(parents=True, exist_ok=True)
    spark = get_spark("build-gold")

    for name, module in QUESTIONS.items():
        tables = {
            table: spark.read.parquet(str(silver / table))
            for table in module.required_tables()
        }
        rows = [row.asDict() for row in module.run(tables).collect()]
        mark = config.gold.get(name, module.default_mark())
        spec = to_vega_lite(rows, module.chart_encoding(), mark=mark, title=name)

        out_path = gold / f"{name}.json"
        out_path.write_text(json.dumps(spec, indent=2))
        log.info("gold: %s -> %s (%d rows, mark=%s)", name, out_path, len(rows), mark)

    spark.stop()


def main() -> None:
    configure()

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default=str(REPO_ROOT / "config.yaml"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="fetch bronze files for the configured wiki/date range")
    sub.add_parser("build-silver", help="parse bronze into the silver tables")
    run_q = sub.add_parser("run-question", help="run one question module against silver")
    run_q.add_argument("name", choices=sorted(QUESTIONS))
    sub.add_parser("build-gold", help="run every question, write each as a Vega-Lite chart spec")

    args = parser.parse_args()
    config = load_config(Path(args.config))

    if args.command == "download":
        cmd_download(config)
    elif args.command == "build-silver":
        cmd_build_silver(config)
    elif args.command == "run-question":
        cmd_run_question(config, args.name)
    elif args.command == "build-gold":
        cmd_build_gold(config)


if __name__ == "__main__":
    main()
