# Design doc: Semiconductor Yield & Test Analytics

| | |
|---|---|
| **Author** | Stanley Igwe |
| **Status** | Built on real SECOM data; Databricks run and live agent benchmark pending |
| **Last updated** | 26 Oct 2026 |

## 1. Problem and users
- **Users:** yield engineers, process engineers, the fab operations lead.
- **Questions they need answered:** What is yield by day and lot, and is today's fail rate out of control? Which sensors separate failing wafers, beyond chance? Which wafers should be inspected first? Can I ask in plain English without getting a silently wrong number?
- **Current pain (assumed scenario):** raw sensor tables with 590 columns, inconsistent yield definitions, silent nulls, and control limits nobody refreshes.

## 2. Requirements
| Type | Requirement |
|---|---|
| Functional | Yield defined once; a daily p-chart; a sensor ranking with multiple-testing checks; a wafer ranking scored on unseen later wafers; guarded natural-language questions |
| Data quality | Key integrity; yield in [0, 1]; fails never exceed wafers; every wafer has readings; constant and mostly-missing sensors flagged, not dropped; control limits only from earlier, passing wafers (unit-tested) |
| Freshness / SLA | Batch: gold rebuilt after each test-run batch. The full real build takes 2.4 s in dbt; the ranking evaluation with 1,000 bootstraps takes about 4 minutes |
| Scale | 1,567 wafers × 590 sensors today (924,530 readings). Design target 10k wafers a day × 2k sensors (~20M readings a day) |
| Cost | £0 locally and in CI (DuckDB, GitHub Actions). Databricks Free Edition for the cloud run |

## 3. Design
- **Layers:** bronze (raw) → silver (typed, long format, reference-period statistics) → gold (Kimball dims and facts, yield aggregates, p-chart, sensor ranking). See `layer_plan.md`.
- **Long (EAV) sensor format** instead of 590 wide columns: sensors come and go by recipe, per-sensor statistics become a GROUP BY, and the table partitions by date and sensor. ML pivots back to wide in `analysis/` only.
- **Control limits come from a reference period.** The first half of runs (784 wafers, 67 fails) is Phase I; limits use its passing wafers only. The scaffold computed limits over all wafers, which judged each wafer partly against the future. A dbt unit test now proves failing and later wafers don't move the limits.
- **Yield definition:** passed wafers / tested wafers, in `agg_yield_*` only. The agent's prompt tells it never to recompute yield.
- **Sensor ranking with honest uncertainty:** Cohen's d, then two checks: Benjamini-Hochberg at 5% (22 sensors pass) and the label-shuffle maximum (5 pass). Only 3 pass both, and the dashboard colours the Pareto by that evidence.
- **Wafer ranking evaluated like production:** fit on the first half, score the later half, report every variant tried with bootstrap intervals.
- **NL-to-SQL guardrail on the database's own parser:** `json_serialize_sql` gives the full syntax tree. The guardrail walks it for every table and function at any depth, so comma joins, subqueries, CTE bodies and file paths can't slip through. Execution is read-only with external access disabled and a 1,000-row cap.

## 4. Options considered
| Decision | Options | Chosen | Why |
|---|---|---|---|
| Sensor storage | Wide / long / map-JSON | Long | Schema stability, per-sensor statistics, partition pruning |
| Compute | Databricks + Delta / Snowflake / DuckDB only | DuckDB locally and in CI; dbt targets Databricks for the cloud | Free, reproducible CI; Delta features in the cloud |
| Control limits | All data / reference period / rolling window | Reference period in dbt; rolling robust limits evaluated in Python | Reference limits are standard SPC and leak nothing; the evaluation shows drift makes them go stale |
| Wafer ranking | Static SPC count / Isolation Forest / supervised, fitted once or walk-forward | Walk-forward gradient boosting | The only method whose ROC AUC interval excludes chance on the later half (0.664, 0.571–0.757) |
| Guardrail | Regex / allow-list views / parser AST + locked-down connection | Parser AST + read-only, no external access | The regex let 6 of 20 attacks through and blocked 1 legitimate query; the parser is 28/28 |

## 5. Failure modes and mitigations
| Failure | Detection | Mitigation |
|---|---|---|
| Late or duplicate test-run batch | Uniqueness test on `run_id`; freshness check | Idempotent MERGE into bronze on `run_id` |
| New sensor appears | `relationships` test from readings to `dim_sensor` fails | Register it in the catalogue as unmapped; alert |
| Process drift makes limits stale | Out-of-control rate on passing wafers (4.4 → 10.9 per wafer between halves) | Refresh limits on a rolling window; walk-forward model refits |
| Chance sensor "signals" | FDR and label-shuffle checks | Only act on sensors that pass both |
| LLM writes valid but wrong SQL | Benchmark regression (30 questions + 6 refusals) | Gold-only schema, yield rule in the prompt, result comparison |
| LLM tries to escape the gold layer | Guardrail adversarial suite in CI | Parser guardrail, read-only connection, external access off |

## 6. Results (real SECOM run, 26 Oct 2026)
| Metric | Baseline | After |
|---|---|---|
| Control limits | All wafers, including later ones (leaky) | Reference-period passing wafers only (unit-tested) |
| Wafer ranking, later half (average precision) | Random 0.042; static SPC count 0.049 | Walk-forward gradient boosting 0.147 (95% CI 0.08–0.263), about 3x the 4.7% base rate |
| Sensors ranked | Top 10 by effect size | 3 sensors pass both noise checks |
| Guardrail | Regex: 21/28 cases | Parser: 28/28 cases |

## 7. Next steps and open questions
- Run the same dbt project on Databricks Free Edition (needs workspace credentials) and record runtime and cost.
- Run the Claude agent on the benchmark (`make agent-eval`, needs Anthropic credentials) and publish execution accuracy.
- Replace the reference-period limits in dbt with rolling limits once a refresh cadence is agreed with process engineers.
