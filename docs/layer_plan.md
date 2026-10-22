# Layer plan: bronze → silver → gold

| Layer | Where (DuckDB / Databricks) | Materialisation | Owner | Contract |
|---|---|---|---|---|
| **Bronze** | schema `bronze` / Delta tables in `bt2.bronze` | Tables written by Python (append or MERGE on key) | Ingestion | Raw values; adds `_loaded_at` and `_source_file` only |
| **Silver: staging** | schema `silver` (dbt `+schema: silver`) | Views | dbt | One `stg_` model per source table: renamed, typed, no joins |
| **Silver: intermediate** | schema `silver` | Tables | dbt | Reusable logic (statistics, scoring); not exposed to BI |
| **Gold: marts** | schema `gold` | Tables (Delta in the cloud). `fct_sensor_reading` is incremental in the cloud. | dbt | Kimball dims and facts plus aggregates; the **only** layer that BI, ML and the NL-to-SQL agent may read |

## Bronze tables
| Table | Grain | Columns | Produced by |
|---|---|---|---|
| `bronze.secom_runs` | one row per run | `run_id`, `label_raw` (-1 pass, 1 fail), `run_ts_raw`, `_source_file`, `_loaded_at` | `build_bronze.py` |
| `bronze.secom_sensor_readings` | one row per run × sensor | `run_id`, `sensor_id`, `reading_value` (NULL when NaN), `_loaded_at` | `build_bronze.py` (wide → long) |
| `bronze.context_lot_wafer_map` | one row per run | `run_id`, `wafer_id`, `lot_id`, `slot_no` | `generate_context.py` (synthetic) |
| `bronze.context_sensor_catalog` | one row per sensor | `sensor_id`, `step_id`, `tool_id`, `parameter_name`, `unit` | `generate_context.py` (synthetic) |
| `bronze.context_tools` | one row per tool | `tool_id`, `tool_type`, `step_id`, `chamber_count` | `generate_context.py` (synthetic) |
| `bronze.context_process_steps` | one row per step | `step_id`, `step_name`, `step_seq` | `generate_context.py` (synthetic) |

## dbt models
### Staging (views)
- `stg_secom__runs`: `run_id`, `is_fail`, `run_ts`, `test_date`
- `stg_secom__sensor_readings`: `run_id`, `sensor_id`, `reading_value`, `is_missing`
- `stg_context__lot_wafer_map`, `stg_context__sensor_catalog`, `stg_context__tools`, `stg_context__process_steps`

### Intermediate (tables)
- `int_sensor_stats` (grain: sensor): n, missing rate, mean, standard deviation, min, max, `is_constant`, `is_mostly_missing`
- `int_readings_scored` (grain: run × sensor): z-score, `is_out_of_control` (|z| > 3; NULL when the sensor is constant or the reading is missing)

### Marts (tables)
- `dim_process_step`, `dim_tool`, `dim_sensor`, `dim_lot`, `dim_wafer`
- `fct_sensor_reading` (grain: run × sensor)
- `fct_wafer_test` (grain: run): `is_fail`, `run_ts`, `lot_id`, `n_missing_readings`, `n_out_of_control`
- `agg_yield_daily` (grain: test date), `agg_yield_by_lot` (grain: lot)
- `rpt_sensor_fail_signal` (grain: sensor): mean for passing vs failing wafers, pooled standard deviation, effect size, rank

## Tests
- **Keys:** `unique` and `not_null` on every primary key; `relationships` for every foreign key.
- **Values:** `accepted_values` on `label_raw` ∈ {-1, 1}.
- **Business rules** (singular tests in `tests/`):
  - `assert_yield_between_0_and_1`
  - `assert_fails_not_exceed_wafers`
  - `assert_every_wafer_has_readings`
  - `assert_lot_wafer_counts_match`
  - `assert_no_future_test_timestamps`

## Databricks specifics (when you run it in the cloud)
- **Schemas:** `bt2.bronze`, `bt2.silver`, `bt2.gold` in Unity Catalog (Free Edition supports Unity Catalog [Check]).
- **`fct_sensor_reading`:** incremental merge on (`run_id`, `sensor_id`) with Liquid Clustering on (`test_date`, `sensor_id`). Record before/after query times in the README.
- **Time travel:** use Delta time travel (`VERSION AS OF`) to show reproducible yield at a past point in time.
