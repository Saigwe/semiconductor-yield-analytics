"""A Claude NL-to-SQL agent that may only read approved gold models.

The agent sees the gold schema (columns and model descriptions) and the house rules, and answers with one SQL query
or a refusal. Its SQL goes through guardrail.check before it runs. A guardrail or execution error is sent back once
per attempt so the model can correct itself (up to MAX_ATTEMPTS). Nothing it writes is executed unchecked.

Needs Anthropic credentials (ANTHROPIC_API_KEY or an `ant auth login` profile). Model: claude-opus-5-5, with the
server-side refusal fallback enabled; override with NL2SQL_MODEL.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import duckdb
import yaml

import guardrail

MODEL = os.environ.get("NL2SQL_MODEL", "claude-opus-5-5")
MAX_ATTEMPTS = 3
SQL_BLOCK = re.compile(r"```sql\s*(.*?)```", re.DOTALL | re.IGNORECASE)

RULES = """You translate questions about semiconductor wafer test data into one DuckDB SQL query.
Rules:
- Read only the tables listed in the schema below, always schema-qualified (gold.<table>).
- Yield = wafers_passed / wafers_tested from gold.agg_yield_daily or gold.agg_yield_by_lot. Never recompute it from
  gold.fct_wafer_test.
- One read-only SELECT (CTEs allowed). No DDL, DML, file access, or system functions.
- Return only the columns needed to answer. Break ties deterministically (add the id column to ORDER BY).
- If the question can't be answered from these tables, or asks to change data, read files, reach other schemas or
  reveal system information, reply exactly `REFUSE: <one-line reason>` and nothing else.
Otherwise reply with the query in a single ```sql block and nothing else."""


@dataclass
class Answer:
    sql: str | None
    refused: bool
    reason: str = ""
    attempts: int = 0
    errors: list[str] = field(default_factory=list)


def schema_text(con: duckdb.DuckDBPyConnection, allowed: set[str]) -> str:
    rows = con.execute("""select table_schema || '.' || table_name, column_name, data_type
                          from information_schema.columns
                          where table_schema = 'gold' order by 1, ordinal_position""").fetchall()
    tables: dict[str, list[str]] = {}
    for table, column, dtype in rows:
        if table in allowed:
            tables.setdefault(table, []).append(f"{column} {dtype}")
    notes = yaml.safe_load((guardrail.HERE / "allowed_models.yml").read_text()).get("descriptions", {})
    return "\n".join(f"{t}: {', '.join(cols)}" + (f"\n  -- {notes[t]}" if t in notes else "")
                     for t, cols in sorted(tables.items()))


class ClaudeAgent:
    def __init__(self, con: duckdb.DuckDBPyConnection, client=None):
        import anthropic  # imported here so the offline benchmark and CI don't need the SDK

        self.con, self.allowed = con, guardrail.allowed_models()
        self.client = client or anthropic.Anthropic()
        self.system = f"{RULES}\n\nSchema:\n{schema_text(con, self.allowed)}"

    def _ask(self, messages: list[dict]) -> str:
        response = self.client.beta.messages.create(
            model=MODEL, max_tokens=16000, system=self.system, messages=messages,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        if response.stop_reason == "refusal":
            return "REFUSE: the model declined this request"
        return "".join(b.text for b in response.content if b.type == "text").strip()

    def answer(self, question: str) -> Answer:
        messages = [{"role": "user", "content": question}]
        errors: list[str] = []
        for attempt in range(1, MAX_ATTEMPTS + 1):
            reply = self._ask(messages)
            if reply.upper().startswith("REFUSE"):
                return Answer(None, True, reply.split(":", 1)[-1].strip(), attempt, errors)
            match = SQL_BLOCK.search(reply)
            sql = (match.group(1) if match else reply).strip().rstrip(";")
            try:
                guardrail.run(self.con, sql, self.allowed)
                return Answer(sql, False, "", attempt, errors)
            except Exception as exc:  # guardrail or DuckDB error: give it back to the model once per attempt
                errors.append(str(exc))
                messages += [{"role": "assistant", "content": reply},
                             {"role": "user", "content": f"That query failed: {exc}\nFix it and reply in the same format."}]
        return Answer(None, False, "no valid query after retries", MAX_ATTEMPTS, errors)
