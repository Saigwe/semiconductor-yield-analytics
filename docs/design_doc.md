# Design doc: Semiconductor Yield & Test Analytics
*A one-page template. Keep it to about one page. Fill in each `TODO` from real decisions and measurements.*

| | |
|---|---|
| **Author** | Stanley Igwe |
| **Status** | Draft / In review / Final |
| **Last updated** | YYYY-MM-DD |

## 1. Problem and users
- **Users:** yield engineers, process engineers, the fab operations lead.
- **Questions they need answered:** What is yield by day and lot? Which sensors shift before failures? Which wafers look anomalous even when they pass?
- **Current pain (assumed scenario):** raw sensor tables with 590 columns, inconsistent yield definitions, and silent nulls.

## 2. Requirements
| Type | Requirement |
|---|---|
| Functional | Yield metric defined once, reused everywhere; sensor-level fail signal; anomaly scores per wafer; natural-language questions |
| Data quality | Primary and foreign key integrity; yield ∈ [0,1]; no fails > wafers; every wafer has readings; missing and constant sensors flagged |
| Freshness / SLA | TODO, e.g. gold refreshed within 15 minutes of a test-run batch landing |
| Scale | 1.6k wafers × 590 sensors today (~925k readings). Design for 10k wafers/day × 2k sensors (~20M readings/day). |
| Cost | TODO, e.g. stay inside Databricks Free Edition; target cost per run on paid compute |

## 3. Design
- **Layers:** bronze (raw, append-only) → silver (typed, renamed, long format) → gold (Kimball dims and facts plus aggregates). See `layer_plan.md`.
- **Key choice: long (EAV) sensor format** instead of 590 wide columns.
  - *Why:* sensors get added and removed by tool and recipe, so a long table avoids schema churn, makes per-sensor statistics a GROUP BY, and lets the table be partitioned and clustered by date and sensor.
  - *Cost:* ML needs a pivot back to wide; that happens in `analysis/` only.
- **Out-of-control flag:** |z| > 3 against per-sensor mean and standard deviation (Shewhart-style).
  - TODO: compare with robust statistics (median/MAD) and justify the choice.
- **Yield definition:** `passed wafers / tested wafers` at the agreed grain. It's defined once in `agg_yield_*`, and BI tools must not recompute it.
- **NL-to-SQL guardrails:** the agent may only query gold models listed in `nl2sql/allowed_models.yml`. Answers are scored by execution accuracy against gold SQL.

## 4. Options considered
| Decision | Options | Chosen | Why |
|---|---|---|---|
| Sensor storage | Wide table / long table / semi-structured (map/JSON) | Long | Schema stability, per-sensor statistics, partition pruning |
| Compute | Databricks + Delta / Snowflake / DuckDB only | DuckDB locally + Databricks in the cloud | Free local CI; Delta features (time travel, OPTIMIZE / Z-ORDER) in the cloud |
| Outlier rule | z-score / MAD / Isolation Forest | z-score in dbt; Isolation Forest in ML | Simple and explainable in SQL; multivariate signal in ML |
| TODO | | | |

## 5. Failure modes and mitigations
| Failure | Detection | Mitigation |
|---|---|---|
| Late or duplicate test-run batch | Uniqueness test on `run_id`; freshness check | Idempotent MERGE into bronze on `run_id` |
| New sensor appears | `relationships` test from readings to `dim_sensor` fails | Auto-register in the catalogue with `step = 'unmapped'`; alert |
| Sensor drift makes z-scores meaningless | Rolling statistics comparison | TODO: rolling-window baselines |
| LLM produces valid but wrong SQL | Benchmark regression in CI | Allowed-model list; result-shape checks |

## 6. Results (fill from real runs)
| Metric | Before / baseline | After |
|---|---|---|
| TODO | | |

## 7. Next steps and open questions
- TODO
