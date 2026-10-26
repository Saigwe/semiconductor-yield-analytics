"""Guardrail, agent loop (with scripted Claude replies, no API call) and ranking helpers, on a finished run (BT2_DB)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "nl2sql"), str(ROOT / "analysis")]
import guardrail  # noqa: E402
from agent import ClaudeAgent  # noqa: E402
from anomaly_detection import precision_at, rolling_spc  # noqa: E402

DB = os.environ.get("BT2_DB", str(ROOT / "warehouse" / "bt2.duckdb"))
CASES = [json.loads(l) for l in (ROOT / "nl2sql" / "guardrail_cases.jsonl").read_text().splitlines() if l.strip()]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_guardrail_case(case):
    allowed = guardrail.allowed_models()
    if case["expect"] == "allow":
        guardrail.check(case["sql"], allowed)
    else:
        with pytest.raises(guardrail.GuardrailError):
            guardrail.check(case["sql"], allowed)


def test_execution_connection_blocks_file_access():
    con = guardrail.connect(DB)
    with pytest.raises(Exception, match="(?i)permission|disabled"):
        con.execute("select * from read_csv('README.md')").fetchall()


class ScriptedClient:
    """Stands in for anthropic.Anthropic(): returns canned replies and records what it was sent."""

    def __init__(self, replies, stop_reason="end_turn"):
        self.replies, self.calls, self.stop_reason = list(replies), [], stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        text = self.replies.pop(0)
        return SimpleNamespace(stop_reason=self.stop_reason, content=[SimpleNamespace(type="text", text=text)])


def test_agent_corrects_itself_after_a_guardrail_rejection():
    client = ScriptedClient(["```sql\nselect count(*) from bronze.secom_runs\n```",
                             "```sql\nselect sum(wafers_tested) from gold.agg_yield_daily\n```"])
    answer = ClaudeAgent(guardrail.connect(DB), client=client).answer("How many wafers were tested?")
    assert answer.sql.startswith("select sum(wafers_tested)") and answer.attempts == 2
    assert "not allowed" in client.calls[1]["messages"][-1]["content"]
    assert client.calls[0]["fallbacks"] == "default" and "gold.agg_yield_daily" in client.calls[0]["system"]


def test_agent_passes_through_refusals():
    agent = ClaudeAgent(guardrail.connect(DB), client=ScriptedClient(["REFUSE: writes are not allowed"]))
    assert agent.answer("Delete all failing wafers").refused
    declined = ClaudeAgent(guardrail.connect(DB), client=ScriptedClient(["x"], stop_reason="refusal"))
    assert declined.answer("anything").refused


def test_agent_gives_up_after_three_bad_queries():
    agent = ClaudeAgent(guardrail.connect(DB), client=ScriptedClient(["select * from bronze.secom_runs"] * 3))
    answer = agent.answer("raw rows please")
    assert answer.sql is None and not answer.refused and len(answer.errors) == 3


def test_precision_at_k_and_rolling_spc():
    assert precision_at(np.array([0.9, 0.8, 0.1, 0.0]), np.array([1, 0, 1, 0]), 2) == 0.5
    rng = np.random.default_rng(0)
    X = rng.normal(size=(80, 3))
    X[-1] = 50.0  # the last wafer is far outside every sensor's history
    scores = rolling_spc(X, np.zeros(80, dtype=int), window=40)
    assert scores[-1] == 3 and scores[:30].sum() == 0  # no limits until 30 passing wafers exist
