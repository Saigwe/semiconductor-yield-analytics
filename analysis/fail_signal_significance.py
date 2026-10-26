"""Is the sensor ranking more than noise? Multiple-testing checks on gold.rpt_sensor_fail_signal.

With ~440 sensors and ~100 fails, some sensors will look different between failing and passing wafers by chance.
Two checks, written to gold.ml_sensor_signal_significance and results/fail_signal.md:
  - Welch t-test per sensor, Benjamini-Hochberg false discovery rate at 5%
  - label-shuffle null: shuffle pass/fail 500 times, take the largest |Cohen's d| across all sensors each time;
    a sensor beats the null when its |d| is above the 95th percentile of that maximum (family-wise 5%)

Usage: python analysis/fail_signal_significance.py --db warehouse/bt2.duckdb --out results
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

SEED, SHUFFLES, FDR = 42, 500, 0.05


def cohens_d(X: np.ndarray, fail: np.ndarray) -> np.ndarray:
    a, b = X[fail], X[~fail]
    na, nb = (~np.isnan(a)).sum(0), (~np.isnan(b)).sum(0)
    pooled = np.sqrt(((na - 1) * np.nanvar(a, 0, ddof=1) + (nb - 1) * np.nanvar(b, 0, ddof=1)) / (na + nb - 2))
    with np.errstate(all="ignore"):
        return (np.nanmean(a, 0) - np.nanmean(b, 0)) / pooled


def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    order = np.argsort(p)
    ranked = p[order] * len(p) / np.arange(1, len(p) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty_like(q)
    out[order] = np.minimum(q, 1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="warehouse/bt2.duckdb")
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    con = duckdb.connect(args.db)
    ranked = con.execute("select sensor_id, parameter_name, step_name, effect_size, signal_rank "
                         "from gold.rpt_sensor_fail_signal order by signal_rank").df()
    long = con.execute("select run_id, sensor_id, reading_value from gold.fct_sensor_reading").df()
    X = long.pivot(index="run_id", columns="sensor_id", values="reading_value")[ranked.sensor_id]
    fail = con.execute("select run_id, is_fail from gold.fct_wafer_test").df().set_index("run_id").loc[X.index, "is_fail"]
    Xv, f = X.to_numpy(), fail.to_numpy()

    p = np.array([stats.ttest_ind(Xv[f, j][~np.isnan(Xv[f, j])], Xv[~f, j][~np.isnan(Xv[~f, j])],
                                  equal_var=False).pvalue for j in range(Xv.shape[1])])
    p = np.nan_to_num(p, nan=1.0)
    q = benjamini_hochberg(p)
    rng = np.random.default_rng(SEED)
    null_max = np.array([np.nanmax(np.abs(cohens_d(Xv, rng.permutation(f)))) for _ in range(SHUFFLES)])
    threshold = float(np.percentile(null_max, 95))
    d = np.abs(ranked.effect_size.to_numpy())

    out = ranked.assign(abs_effect_size=d, p_value=p, q_value=q, passes_fdr=q < FDR, beats_shuffle_max=d > threshold)
    con.register("sig_df", out)
    con.execute("create or replace table gold.ml_sensor_signal_significance as select * from sig_df")
    summary = {"sensors_tested": len(out), "fails": int(f.sum()), "passes": int((~f).sum()),
               "pass_fdr_5pct": int(out.passes_fdr.sum()), "beat_shuffle_max_95pct": int(out.beats_shuffle_max.sum()),
               "shuffle_max_abs_d_95pct": round(threshold, 3), "shuffles": SHUFFLES,
               "top10": out.head(10)[["signal_rank", "sensor_id", "parameter_name", "effect_size", "q_value",
                                      "beats_shuffle_max"]].round(4).to_dict("records")}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "fail_signal.json").write_text(json.dumps(summary, indent=2, default=str))
    lines = ["# Sensor fail signal: is it more than noise?\n",
             f"{summary['sensors_tested']} usable sensors, {summary['fails']} failing and {summary['passes']} passing wafers.\n",
             f"- {summary['pass_fdr_5pct']} sensors pass a 5% false discovery rate (Welch t-test, Benjamini-Hochberg).",
             f"- {summary['beat_shuffle_max_95pct']} sensors have |d| above {threshold:.3f}, the 95th percentile of the "
             f"largest |d| across all sensors when pass/fail labels are shuffled ({SHUFFLES} times).\n",
             "| Rank | Sensor | Synthetic name | Cohen's d | q value | Beats shuffle max |", "|---:|---:|---|---:|---:|---|"]
    lines += [f"| {r.signal_rank} | {r.sensor_id} | {r.parameter_name} | {r.effect_size:.3f} | {r.q_value:.4f} | "
              f"{'yes' if r.beats_shuffle_max else 'no'} |" for r in out.head(15).itertuples()]
    (args.out / "fail_signal.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:5]))


if __name__ == "__main__":
    main()
