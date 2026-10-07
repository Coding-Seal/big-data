"""SparkSession bootstrap -- one place to change master/config, per
docs/arch/layered-design.md.
"""
from pyspark.sql import SparkSession


def get_spark(app_name: str) -> SparkSession:
    spark = (
        SparkSession.builder.master("local[*]")
        .appName(app_name)
        .config("spark.sql.shuffle.partitions", "8")
        # Overwrite only the partitions a write actually touches, not the
        # whole table -- lets silver-building be re-run after more bronze
        # data shows up without wiping out what's already there.
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark
