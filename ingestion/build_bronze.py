"""Load SECOM raw files into the DuckDB bronze schema.

secom.data         -> bronze.secom_sensor_readings (long format: run_id, sensor_id, reading_value)
secom_labels.data  -> bronze.secom_runs            (run_id, label_raw, run_ts_raw)

Runs are numbered by file row order (1-based), which is how SECOM links features to labels.
"""
import argparse
import datetime as dt
import pathlib
import re

import duckdb
import pandas as pd

LABEL_LINE = re.compile(r'^\s*(-?1)\s+"?([^"]+?)"?\s*$')


def read_runs(path: pathlib.Path) -> pd.DataFrame:
    rows = []
    for i, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        m = LABEL_LINE.match(line)
        if not m:
            raise ValueError(f"{path.name}:{i} unexpected label line: {line!r}")
        rows.append((i, int(m.group(1)), m.group(2).strip()))
    return pd.DataFrame(rows, columns=["run_id", "label_raw", "run_ts_raw"])


def read_readings(path: pathlib.Path) -> pd.DataFrame:
    # Whitespace-separated floats; NaN marks missing values.
    wide = pd.read_csv(path, sep=r"\s+", header=None, na_values=["NaN"], engine="python")
    wide.index = wide.index + 1
    wide.columns = [c + 1 for c in wide.columns]
    long = (
        wide.rename_axis("run_id")
        .reset_index()
        .melt(id_vars="run_id", var_name="sensor_id", value_name="reading_value")
    )
    long["sensor_id"] = long["sensor_id"].astype("int32")
    return long


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--db", default="warehouse/bt2.duckdb")
    args = parser.parse_args()

    raw = pathlib.Path(args.raw_dir)
    runs = read_runs(raw / "secom_labels.data")
    readings = read_readings(raw / "secom.data")
    if runs["run_id"].max() != readings["run_id"].max():
        raise SystemExit("Label and feature files have different row counts")

    loaded_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    runs["_source_file"] = "secom_labels.data"
    runs["_loaded_at"] = loaded_at
    readings["_loaded_at"] = loaded_at

    pathlib.Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(args.db)
    con.execute("create schema if not exists bronze")
    con.register("runs_df", runs)
    con.register("readings_df", readings)
    # Full refresh keeps reruns idempotent; the Databricks loader uses MERGE instead.
    con.execute("create or replace table bronze.secom_runs as select * from runs_df")
    con.execute("create or replace table bronze.secom_sensor_readings as select * from readings_df")
    n_runs = con.execute("select count(*) from bronze.secom_runs").fetchone()[0]
    n_readings = con.execute("select count(*) from bronze.secom_sensor_readings").fetchone()[0]
    con.close()
    print(f"bronze loaded: {n_runs} runs, {n_readings} sensor readings -> {args.db}")


if __name__ == "__main__":
    main()
