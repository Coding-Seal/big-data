"""SparkSession bootstrap -- one place to change master/config, per
docs/arch/layered-design.md. Tuning rationale and measurements live in
AGENTS.md; this file just applies them.
"""
import os

from pyspark.sql import SparkSession

# Must be an env var, not .config(): `local[*]` fixes the driver heap when
# the JVM launches. enwiki needs 6g; simplewiki is fine on the 1g default.
DRIVER_MEMORY_ENV = "SPARK_DRIVER_MEMORY"

# A ceiling on parallelism, not a target -- AQE only coalesces downward, so
# too low a value cannot be raised back up for a big shuffle. Leave
# spark.shuffle.file.buffer at its 32k default: at 200 partitions Spark uses
# BypassMergeSortShuffleWriter, which opens one buffered writer per
# partition at once, so raising it OOMs the 1g default heap (AGENTS.md).
SHUFFLE_PARTITIONS = "200"


def get_spark(app_name: str) -> SparkSession:
    memory = os.environ.get(DRIVER_MEMORY_ENV)
    if memory:
        os.environ["PYSPARK_SUBMIT_ARGS"] = f"--driver-memory {memory} pyspark-shell"

    spark = (
        SparkSession.builder.master("local[*]")
        .appName(app_name)
        .config("spark.sql.shuffle.partitions", SHUFFLE_PARTITIONS)
        # Explicit because SHUFFLE_PARTITIONS is only safe if AQE coalesces it.
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        # Overwrite only the partitions a write touches, so silver can be
        # rebuilt incrementally as more bronze arrives.
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark
