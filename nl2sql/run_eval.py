"""Benchmark for NL-to-SQL over the gold layer, plus the guardrail's adversarial suite.

  --self-check   use each item's gold SQL as the prediction: proves every gold query runs and passes the guardrail
  --guardrail    score guardrail.check (and, for comparison, the legacy regex check) on nl2sql/guardrail_cases.jsonl
  --agent claude run the Claude agent on every question (needs Anthropic credentials; costs a few cents a run)

A SQL item is correct when the prediction's result equals the gold SQL's result (order-insensitive, floats rounded
to 6 places). A refusal item ("expect": "refuse") is correct when the agent refuses. Results go to results/.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import guardrail

HERE = Path(__file__).parent


def normalise(rows: list[tuple]) -> list[tuple]:
    return sorted((tuple(round(v, 6) if isinstance(v, float) else v for v in r) for r in rows), key=repr)


def score_guardrail(out: Path) -> dict:
    allowed = guardrail.allowed_models()
    cases = [json.loads(l) for l in (HERE / "guardrail_cases.jsonl").read_text().splitlines() if l.strip()]
    rows, totals = [], {"parser": 0, "legacy_regex": 0}
    for c in cases:
        verdicts = {}
        for name, fn in (("parser", guardrail.check), ("legacy_regex", guardrail.legacy_regex_guardrail)):
            try:
                fn(c["sql"], allowed)
                verdicts[name] = "allow"
            except Exception:
                verdicts[name] = "reject"
            totals[name] += verdicts[name] == c["expect"]
        rows.append({**c, **verdicts})
    bad = [r for r in rows if r["expect"] == "reject"]
    ok = [r for r in rows if r["expect"] == "allow"]
    summary = {"cases": len(rows), "attacks": len(bad), "legitimate": len(ok),
               "parser_correct": totals["parser"], "legacy_correct": totals["legacy_regex"],
               "legacy_attacks_let_through": [r["id"] for r in bad if r["legacy_regex"] == "allow"],
               "legacy_legit_blocked": [r["id"] for r in ok if r["legacy_regex"] == "reject"],
               "parser_errors": [r["id"] for r in rows if r["parser"] != r["expect"]]}
    lines = ["# Guardrail: adversarial suite\n",
             f"{summary['cases']} cases: {summary['attacks']} attacks and {summary['legitimate']} legitimate queries.\n",
             f"- Parser-based guardrail: **{summary['parser_correct']}/{summary['cases']}** correct.",
             f"- Legacy regex guardrail: {summary['legacy_correct']}/{summary['cases']}; it let "
             f"{len(summary['legacy_attacks_let_through'])} attacks through and blocked "
             f"{len(summary['legacy_legit_blocked'])} legitimate query.\n",
             "| Case | Expect | Parser | Legacy regex | SQL |", "|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['expect']} | {r['parser']} | {r['legacy_regex']} | `{r['sql'].replace('|', '¦')}` |"
              for r in rows]
    (out / "guardrail.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "guardrail.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="warehouse/bt2.duckdb")
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--guardrail", action="store_true")
    ap.add_argument("--agent", choices=["claude"])
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    if args.guardrail:
        s = score_guardrail(args.out)
        print(f"guardrail: parser {s['parser_correct']}/{s['cases']}, legacy regex {s['legacy_correct']}/{s['cases']}")
        if s["parser_errors"]:
            raise SystemExit(f"guardrail wrong on {s['parser_errors']}")

    if not (args.self_check or args.agent):
        return
    con = guardrail.connect(args.db)
    items = [json.loads(l) for l in (HERE / "benchmark.jsonl").read_text().splitlines() if l.strip()]
    agent = None
    if args.agent == "claude":
        from agent import ClaudeAgent
        agent = ClaudeAgent(con)

    results = []
    for item in items:
        refuse_item = item.get("expect") == "refuse"
        t0 = time.perf_counter()
        if args.self_check:
            if refuse_item:
                continue
            ans_sql, refused, attempts, errors = item["gold_sql"], False, 1, []
        else:
            a = agent.answer(item["question"])
            ans_sql, refused, attempts, errors = a.sql, a.refused, a.attempts, a.errors
        try:
            if refuse_item:
                ok = refused
            else:
                ok = (not refused and ans_sql is not None and
                      normalise(guardrail.run(con, ans_sql)) == normalise(guardrail.run(con, item["gold_sql"])))
        except Exception as exc:
            ok, errors = False, errors + [str(exc)]
        results.append({"id": item["id"], "correct": bool(ok), "refused": refused, "attempts": attempts,
                        "sql": ans_sql, "errors": errors, "latency_s": round(time.perf_counter() - t0, 2)})

    sql_items = [r for r in results if not r["id"].startswith("r")]
    ref_items = [r for r in results if r["id"].startswith("r")]
    summary = {"mode": "self-check" if args.self_check else args.agent,
               "sql_correct": sum(r["correct"] for r in sql_items), "sql_total": len(sql_items),
               "refusals_correct": sum(r["correct"] for r in ref_items), "refusals_total": len(ref_items),
               "first_attempt": sum(r["correct"] and r["attempts"] == 1 for r in results), "results": results}
    name = "nl2sql_self_check.json" if args.self_check else f"nl2sql_{args.agent}.json"
    (args.out / name).write_text(json.dumps(summary, indent=2, default=str))
    print(f"{summary['mode']}: SQL {summary['sql_correct']}/{summary['sql_total']} correct, "
          f"refusals {summary['refusals_correct']}/{summary['refusals_total']}")
    if args.self_check and summary["sql_correct"] != summary["sql_total"]:
        raise SystemExit("gold SQL failed the self-check")


if __name__ == "__main__":
    main()
