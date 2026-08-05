from __future__ import annotations

import sys

from pyspark.sql import SparkSession


def test_official_glue_compatibility_runtime() -> None:
    spark = SparkSession.builder.master("local[1]").appName("cryptopulse-phase1").getOrCreate()
    try:
        assert sys.version_info[:2] == (3, 11)
        assert spark.version.startswith("3.5.")
    finally:
        spark.stop()
