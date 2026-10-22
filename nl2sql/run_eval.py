"""Execution-accuracy benchmark for an NL-to-SQL agent over the gold layer.

A prediction is correct when its result set equals the gold SQL's result set (order-insensitive,
floats rounded). Plug your agent into `generate_sql`. The guardrail rejects SQL that is not a
single SELECT, or that touches tables outside nl2sql/allowed_models.yml.
"""
import argparse
import json
import pathlib
import re
import time

import duckdb
import yaml

HERE = pathlib.Path(__file__).parent
TABLE_REF = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][\w.]*)", re.IGNORECASE)


def generate_sql(question: str) -> str:
    """TODO: call your agent here (e.g. an LLM given the gold schema and dbt docs)."""
    raise NotImplementedError("Implement the agent, or run with --self-check to validate the benchmark.")


def guardrail(sql: str, allowed: set[str]) -> None:
    stripped = sql.strip().rstrip(";")
    if ";" in stripped or not re.match(r"^\s*(with|select)\b", stripped, re.IGNORECASE):
        raise ValueError("only a single SELECT statement is allowed")
    used = {t.lower() for t in TABLE_REF.findall(stripped)}
    ctes = {m.lower() for m in re.findall(r"\b(\w+)\s+as\s*\(", stripped, re.IGNORECASE)}
    illegal = used - allowed - ctes
    if illegal:
        raise ValueError(f"tables not allowed: {sorted(illegal)}")


def normalise(rows: list[tuple]) -> list[tuple]:
    return sorted(tuple(round(v, 6) if isinstance(v, float) else v for v in r) for r in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="warehouse/bt2.duckdb")
    parser.add_argument("--self-check", action="store_true",
                        help="use gold SQL as the prediction to validate that the benchmark runs")
    args = parser.parse_args()

    allowed = {m.lower() for m in yaml.safe_load((HERE / "allowed_models.yml").read_text())["allowed_models"]}
    items = [json.loads(line) for line in (HERE / "benchmark.jsonl").read_text().splitlines() if line.strip()]
    con = duckdb.connect(args.db, read_only=True)

    correct, results = 0, []
    for item in items:
        t0 = time.perf_counter()
        try:
            pred = item["gold_sql"] if args.self_check else generate_sql(item["question"])
            guardrail(pred, allowed)
            ok = normalise(con.execute(pred).fetchall()) == normalise(con.execute(item["gold_sql"]).fetchall())
            err = None
        except NotImplementedError:
            raise
        except Exception as exc:  # a failed prediction counts as wrong, but is reported
            ok, err = False, str(exc)
        correct += ok
        results.append({"id": item["id"], "correct": ok, "error": err,
                        "latency_s": round(time.perf_counter() - t0, 3)})

    con.close()
    for r in results:
        print(r)
    print(f"execution accuracy: {correct}/{len(items)} = {correct / len(items):.1%}")


if __name__ == "__main__":
    main()
