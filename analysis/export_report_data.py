"""Export small aggregates of the real-data run to CSV for the Evidence.dev dashboard (reports/sources/secom).

They're committed, so CI can build the dashboard without downloading SECOM.

Usage: python analysis/export_report_data.py --db warehouse/bt2.duckdb --results results
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd

QUERIES = {
    "kpis": """select (select count(*) from gold.fct_wafer_test) as wafers,
                      (select sum(wafers_failed) from gold.agg_yield_daily) as fails,
                      (select sum(wafers_passed) * 1.0 / sum(wafers_tested) from gold.agg_yield_daily) as yield_rate,
                      (select count(*) from gold.dim_sensor) as sensors,
                      (select count(*) from gold.dim_sensor where is_usable) as usable_sensors,
                      (select count(*) from gold.rpt_yield_p_chart where is_above_limit) as days_above_limit""",
    "yield_p_chart": "select * from gold.rpt_yield_p_chart order by test_date",
    "yield_by_lot": "select * from gold.agg_yield_by_lot order by lot_id",
    "sensor_signal": """select s.signal_rank, s.sensor_id, s.parameter_name, s.step_name, s.effect_size,
                               s.abs_effect_size, s.q_value, s.passes_fdr, s.beats_shuffle_max
                        from gold.ml_sensor_signal_significance s order by s.signal_rank limit 30""",
    "ooc_by_period": """select case when is_reference_period then 'Reference (first half)' else 'Later half' end as period,
                               case when is_fail then 'Fail' else 'Pass' end as outcome,
                               avg(n_out_of_control) as avg_out_of_control, count(*) as wafers
                        from gold.fct_wafer_test group by all order by all""",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="warehouse/bt2.duckdb")
    ap.add_argument("--results", type=Path, default=Path("results"))
    ap.add_argument("--out", type=Path, default=Path("reports/sources/secom"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(args.db, read_only=True)
    for name, sql in QUERIES.items():
        df = con.execute(sql).df()
        df.to_csv(args.out / f"{name}.csv", index=False)
        print(f"{name}.csv  {len(df)} rows")

    ev = json.loads((args.results / "anomaly_eval.json").read_text())
    methods = pd.DataFrame([{"method": m, **{k: v for k, v in r.items() if not k.endswith("_ci")},
                             "roc_auc_low": r["roc_auc_ci"][0], "roc_auc_high": r["roc_auc_ci"][1],
                             "ap_low": r["average_precision_ci"][0], "ap_high": r["average_precision_ci"][1],
                             "base_rate": ev["test_base_rate"]} for m, r in ev["methods"].items()])
    methods.to_csv(args.out / "ranking_methods.csv", index=False)
    g = json.loads((args.results / "guardrail.json").read_text())
    pd.DataFrame([{"guardrail": "Parser-based guardrail", "correct": g["parser_correct"], "cases": g["cases"]},
                  {"guardrail": "Legacy regex guardrail", "correct": g["legacy_correct"], "cases": g["cases"]}]
                 ).to_csv(args.out / "guardrail.csv", index=False)
    print("ranking_methods.csv, guardrail.csv")


if __name__ == "__main__":
    main()
