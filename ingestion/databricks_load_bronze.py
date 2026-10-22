# Databricks notebook source
# MAGIC %md
# MAGIC # Load SECOM into `bt2.bronze` (Delta)
# MAGIC Upload `secom.data` and `secom_labels.data` to a Unity Catalog volume first, e.g.
# MAGIC `/Volumes/bt2/bronze/raw/`. Then run this notebook. Context tables can be produced by
# MAGIC running `generate_context.py` logic here, or by uploading its output as CSV.

# COMMAND ----------
from pyspark.sql import Window
from pyspark.sql import functions as F

RAW = "/Volumes/bt2/bronze/raw"
# File line number, 1-based. monotonically_increasing_id() preserves read order but is not
# consecutive across partitions, so rank it to get dense line numbers.
LINE_NO = F.row_number().over(Window.orderBy(F.monotonically_increasing_id()))
spark.sql("create schema if not exists bt2.bronze")

# COMMAND ----------
# Labels: `-1 "19/07/2008 11:55:00"` -> run_id is the 1-based line number.
labels = (
    spark.read.text(f"{RAW}/secom_labels.data")
    .withColumn("run_id", LINE_NO)
    .select(
        "run_id",
        F.regexp_extract("value", r"^\s*(-?1)", 1).cast("int").alias("label_raw"),
        F.regexp_extract("value", r'"([^"]+)"', 1).alias("run_ts_raw"),
        F.lit("secom_labels.data").alias("_source_file"),
        F.current_timestamp().alias("_loaded_at"),
    )
)

# Features: whitespace-separated; NaN = missing. Explode to long format.
features = (
    spark.read.text(f"{RAW}/secom.data")
    .withColumn("run_id", LINE_NO)
    .withColumn("vals", F.split(F.trim("value"), r"\s+"))
    .select("run_id", F.posexplode("vals").alias("pos", "raw"))
    .select(
        "run_id",
        (F.col("pos") + 1).cast("int").alias("sensor_id"),
        F.when(F.col("raw") == "NaN", None).otherwise(F.col("raw").cast("double")).alias("reading_value"),
        F.current_timestamp().alias("_loaded_at"),
    )
)

# COMMAND ----------
# Idempotent upsert on natural keys (TODO: switch to MERGE once incremental loads exist).
labels.write.mode("overwrite").saveAsTable("bt2.bronze.secom_runs")
features.write.mode("overwrite").saveAsTable("bt2.bronze.secom_sensor_readings")
display(spark.sql("select count(*) as runs from bt2.bronze.secom_runs"))
