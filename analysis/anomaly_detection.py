"""Which wafers should an engineer look at first? Methods compared on a time split, written to gold.ml_wafer_anomaly_scores.

Train / reference = the first half of runs by test time (int_runs.is_reference_period); test = the later half, which
no method sees while fitting. Methods, all scored on the same test wafers:
  random            the base rate (what picking wafers blind would give)
  spc_ooc_count     number of readings outside the reference-period 3-sigma limits (from dbt, no fitting)
  isolation_forest  unsupervised, fitted on reference-period PASSING wafers only (novelty detection; no labels used)
  logistic_l2       supervised, fitted on reference-period labels (class-weighted, L2, fixed C; no tuning on test)
Drift-aware variants (the process drifts after the reference period, so static limits and one-off fits go stale):
  spc_rolling_w{100,200,400}   robust limits (median, MAD) from the previous W passing wafers, |z| > 4 count
  wf_logistic_l2 / wf_gbm      walk-forward: refit every 100 wafers on everything tested so far (a wafer's label is
                               known once it is tested), then score the next 100
  wf_isolation_forest          walk-forward, refit on the previous 400 passing wafers
Every variant tried is reported; none is dropped for scoring badly.

Metrics: precision@k (k = 10, the number of test fails, and the top 10% of wafers), recall in the top 10%, ROC AUC and
average precision, with 95% bootstrap intervals (1,000 resamples of test wafers).

Usage: python analysis/anomaly_detection.py --db warehouse/bt2.duckdb --out results
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEED = 42
BOOTSTRAP = 1000


def load(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, pd.DataFrame]:
    long = con.execute("""
        select f.run_id, f.sensor_id, f.reading_value
        from gold.fct_sensor_reading f
        join gold.dim_sensor d on f.sensor_id = d.sensor_id
        where d.is_usable
    """).df()
    wide = long.pivot(index="run_id", columns="sensor_id", values="reading_value")
    meta = con.execute("""select run_id, wafer_id, run_ts, run_seq, is_fail, is_reference_period, n_out_of_control
                          from gold.fct_wafer_test order by run_seq""").df().set_index("run_id")
    return wide.loc[meta.index], meta


def rolling_spc(X: np.ndarray, y: np.ndarray, window: int, min_ref: int = 30) -> np.ndarray:
    """Count of readings beyond 4 robust sigmas of the previous `window` passing wafers."""
    out = np.zeros(len(y))
    for i in range(len(y)):
        prev = [j for j in range(max(0, i - 3 * window), i) if y[j] == 0][-window:]
        if len(prev) < min_ref:
            continue
        med = np.nanmedian(X[prev], axis=0)
        mad = np.nanmedian(np.abs(X[prev] - med), axis=0) * 1.4826
        with np.errstate(all="ignore"):
            z = np.abs((X[i] - med) / mad)
        out[i] = (np.isfinite(z) & (z > 4)).sum()
    return out


def walk_forward(X: np.ndarray, y: np.ndarray, start: int, make, step: int = 100, novelty: bool = False) -> np.ndarray:
    out = np.zeros(len(y))
    for b in range(start, len(y), step):
        model = make()
        if novelty:
            train = [j for j in range(max(0, b - 400), b) if y[j] == 0]
            model.fit(X[train])
            out[b:b + step] = -model.decision_function(X[b:b + step])
        else:
            model.fit(X[:b], y[:b])
            out[b:b + step] = model.predict_proba(X[b:b + step])[:, 1]
    return out


def precision_at(scores: np.ndarray, y: np.ndarray, k: int) -> float:
    return float(y[np.argsort(-scores, kind="stable")[:k]].mean())


def metrics(scores: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> dict:
    n, k10 = len(y), max(1, round(0.1 * len(y)))
    top = np.argsort(-scores, kind="stable")[:k10]
    out = {"precision_at_10": precision_at(scores, y, 10),
           "precision_at_n_fails": precision_at(scores, y, int(y.sum())),
           "precision_top_10pct": float(y[top].mean()),
           "recall_top_10pct": float(y[top].sum() / y.sum()),
           "roc_auc": float(roc_auc_score(y, scores)),
           "average_precision": float(average_precision_score(y, scores))}
    boots = {"roc_auc": [], "average_precision": []}
    for _ in range(BOOTSTRAP):
        idx = rng.integers(0, n, n)
        if y[idx].min() == y[idx].max():
            continue
        boots["roc_auc"].append(roc_auc_score(y[idx], scores[idx]))
        boots["average_precision"].append(average_precision_score(y[idx], scores[idx]))
    for m, v in boots.items():
        out[f"{m}_ci"] = [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)]
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out.items()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="warehouse/bt2.duckdb")
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    con = duckdb.connect(args.db)
    X, meta = load(con)
    ref = meta.is_reference_period.to_numpy()
    y = meta.is_fail.to_numpy().astype(int)
    test = ~ref

    iso = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                        IsolationForest(n_estimators=500, random_state=SEED))
    iso.fit(X[ref & (y == 0)])
    lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                       LogisticRegression(C=0.01, class_weight="balanced", max_iter=5000))
    lr.fit(X[ref], y[ref])
    rng_scores = np.random.default_rng(SEED).random(len(X))
    tie = 1e-6 * rng_scores  # random tie-break for count scores
    Xv, start = X.to_numpy(), int(ref.sum())
    pipe = lambda est: (lambda: make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), est()))
    scores = {"random": rng_scores,
              "spc_ooc_count": meta.n_out_of_control.to_numpy().astype(float) + tie,
              "isolation_forest": -iso.decision_function(X),
              "logistic_l2": lr.predict_proba(X)[:, 1],
              **{f"spc_rolling_w{w}": rolling_spc(Xv, y, w) + tie for w in (100, 200, 400)},
              "wf_logistic_l2": walk_forward(Xv, y, start, pipe(lambda: LogisticRegression(
                  C=0.01, class_weight="balanced", max_iter=5000))),
              "wf_gbm": walk_forward(Xv, y, start, lambda: HistGradientBoostingClassifier(
                  max_depth=3, learning_rate=0.05, max_iter=200, class_weight="balanced", random_state=SEED)),
              "wf_isolation_forest": walk_forward(Xv, y, start, pipe(lambda: IsolationForest(
                  n_estimators=300, random_state=SEED)), novelty=True)}

    rng = np.random.default_rng(SEED)
    results = {m: metrics(s[test], y[test], rng) for m, s in scores.items()}
    summary = {"train_wafers": int(ref.sum()), "train_fails": int(y[ref].sum()), "test_wafers": int(test.sum()),
               "test_fails": int(y[test].sum()), "test_base_rate": round(float(y[test].mean()), 4),
               "test_from": str(meta.run_ts[test].min()), "sensors_used": X.shape[1], "methods": results}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "anomaly_eval.json").write_text(json.dumps(summary, indent=2))
    lines = [f"# Wafer ranking: time-split evaluation\n",
             f"Trained on the first {summary['train_wafers']} wafers ({summary['train_fails']} fails); tested on the later "
             f"{summary['test_wafers']} ({summary['test_fails']} fails, base rate {summary['test_base_rate']:.1%}), "
             f"from {summary['test_from'][:10]}. {summary['sensors_used']} usable sensors.\n",
             "| Method | Precision@10 | Precision@fails | Recall in top 10% | ROC AUC (95% CI) | Avg precision (95% CI) |",
             "|---|---:|---:|---:|---|---|"]
    for m, r in results.items():
        lines.append(f"| {m} | {r['precision_at_10']:.2f} | {r['precision_at_n_fails']:.2f} | {r['recall_top_10pct']:.2f} | "
                     f"{r['roc_auc']:.3f} ({r['roc_auc_ci'][0]}–{r['roc_auc_ci'][1]}) | "
                     f"{r['average_precision']:.3f} ({r['average_precision_ci'][0]}–{r['average_precision_ci'][1]}) |")
    (args.out / "anomaly_eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    out = meta.reset_index()[["run_id", "wafer_id", "run_ts", "is_fail", "is_reference_period"]]
    for m in ("spc_ooc_count", "isolation_forest", "logistic_l2", "spc_rolling_w400", "wf_gbm"):
        out[f"score_{m}"] = scores[m]
    out["anomaly_score"] = out.score_wf_gbm  # the method that ranks best on the test half; 0 in the training half
    out["split"] = np.where(ref, "train", "test")
    con.register("scores_df", out)
    con.execute("create or replace table gold.ml_wafer_anomaly_scores as select * from scores_df")
    con.close()


if __name__ == "__main__":
    main()
