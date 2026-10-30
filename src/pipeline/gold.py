"""Gold stage: question results as Vega-Lite chart specs.

Data and encoding come from the question module; the mark type comes from
config.yaml's `gold:` section if set, else the module's default_mark() --
so changing a chart's type is a config edit, not a code change.
"""
import json
import logging

from common.charts import to_vega_lite
from common.spark import get_spark
from config import Config
from questions import QUESTIONS

from . import silver
from .storage import gold_dir

log = logging.getLogger(__name__)


def build(config: Config) -> None:
    gold = gold_dir(config)
    gold.mkdir(parents=True, exist_ok=True)
    spark = get_spark("build-gold")

    for name, module in QUESTIONS.items():
        rows = [
            row.asDict()
            for row in module.run(silver.read_tables(spark, module, config)).collect()
        ]
        mark = config.gold.get(name, module.default_mark())
        spec = to_vega_lite(rows, module.chart_encoding(), mark=mark, title=name)

        out_path = gold / f"{name}.json"
        out_path.write_text(json.dumps(spec, indent=2))
        log.info("gold: %s -> %s (%d rows, mark=%s)", name, out_path, len(rows), mark)

    spark.stop()


def show_question(config: Config, name: str) -> None:
    """One question's result to stdout, for iterating without writing gold."""
    spark = get_spark(f"question-{name}")
    module = QUESTIONS[name]
    module.run(silver.read_tables(spark, module, config)).show(20, truncate=False)
    spark.stop()
