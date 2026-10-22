"""Multivariate wafer anomaly scores with Isolation Forest, written to gold.ml_wafer_anomaly_scores.

Unsupervised: labels are NOT used for training, only for evaluation (precision@k against failing wafers),
with a time-ordered split so the model never sees the future.
"""
import argparse

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load_features(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, pd.DataFrame]:
    long = con.execute("""
        select f.run_id, f.sensor_id, f.reading_value
        from gold.fct_sensor_reading f
        join gold.dim_sensor d on f.sensor_id = d.sensor_id
        where d.is_usable
    """).df()
    wide = long.pivot(index="run_id", columns="sensor_id", values="reading_value").sort_index()
    meta = con.execute(
        "select run_id, wafer_id, run_ts, is_fail from gold.fct_wafer_test order by run_ts, run_id"
    ).df().set_index("run_id")
    return wide.loc[meta.index], meta


def precision_at_k(scores: np.ndarray, is_fail: np.ndarray, k: int) -> float:
    top = np.argsort(-scores)[:k]
    return float(is_fail[top].mean()) if k else float("nan")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="warehouse/bt2.duckdb")
    parser.add_argument("--train-frac", type=float, default=0.7)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    con = duckdb.connect(args.db)
    X, meta = load_features(con)
    split = int(len(X) * args.train_frac)

    model = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        IsolationForest(n_estimators=300, contamination="auto", random_state=args.seed),
    )
    model.fit(X.iloc[:split])
    scores = -model.decision_function(X)  # higher = more anomalous

    test_scores, test_fail = scores[split:], meta["is_fail"].to_numpy()[split:]
    k = max(1, int(test_fail.sum()))
    p_at_k = precision_at_k(test_scores, test_fail, k)
    base_rate = float(test_fail.mean()) if len(test_fail) else float("nan")
    print(f"test wafers={len(test_fail)} fails={int(test_fail.sum())} "
          f"precision@{k}={p_at_k:.3f} (base rate {base_rate:.3f})")

    out = meta.reset_index()[["run_id", "wafer_id", "run_ts", "is_fail"]]
    out["anomaly_score"] = scores
    out["split"] = ["train"] * split + ["test"] * (len(out) - split)
    con.register("scores_df", out)
    con.execute("create or replace table gold.ml_wafer_anomaly_scores as select * from scores_df")
    con.close()


if __name__ == "__main__":
    main()
