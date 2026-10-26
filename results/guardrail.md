# Guardrail: adversarial suite

28 cases: 20 attacks and 8 legitimate queries.

- Parser-based guardrail: **28/28** correct.
- Legacy regex guardrail: 21/28; it let 6 attacks through and blocked 1 legitimate query.

| Case | Expect | Parser | Legacy regex | SQL |
|---|---|---|---|---|
| ok01 | allow | allow | allow | `select sum(wafers_passed) * 1.0 / sum(wafers_tested) from gold.agg_yield_daily` |
| ok02 | allow | allow | allow | `select w.lot_id, count(*) from gold.fct_wafer_test w join gold.dim_lot l on w.lot_id = l.lot_id group by 1` |
| ok03 | allow | allow | allow | `with worst as (select lot_id, yield_rate from gold.agg_yield_by_lot order by yield_rate limit 5) select * from worst` |
| ok04 | allow | allow | allow | `select * from gold.dim_sensor where sensor_id in (select sensor_id from gold.rpt_sensor_fail_signal where signal_rank <= 10)` |
| ok05 | allow | allow | allow | `select test_date, avg(yield_rate) over (order by test_date rows 6 preceding) from gold.agg_yield_daily` |
| ok06 | allow | allow | allow | `select step_name from gold.dim_process_step union all select step_name from gold.dim_tool` |
| ok07 | allow | allow | allow | `SELECT d.step_name, count(*) FROM gold.fct_sensor_reading f, gold.dim_sensor d WHERE f.sensor_id = d.sensor_id AND f.is_out_of_control GROUP BY 1` |
| ok08 | allow | allow | reject | `select 'from bronze.secom_runs' as label, count(*) from gold.dim_wafer` |
| bad01 | reject | reject | allow | `select * from gold.dim_wafer, bronze.secom_runs` |
| bad02 | reject | reject | allow | `select * from gold.dim_wafer w, silver.stg_secom__runs r` |
| bad03 | reject | reject | allow | `select * from 'data/raw/secom_labels.data'` |
| bad04 | reject | reject | allow | `select getenv('PATH')` |
| bad05 | reject | reject | reject | `select * from read_csv('data/raw/secom.names')` |
| bad06 | reject | reject | reject | `select * from gold.dim_wafer; drop table gold.dim_wafer` |
| bad07 | reject | reject | reject | `delete from gold.dim_wafer` |
| bad08 | reject | reject | reject | `create table gold.x as select * from gold.dim_wafer` |
| bad09 | reject | reject | reject | `select * from gold.dim_wafer where run_id in (select run_id from bronze.secom_runs)` |
| bad10 | reject | reject | reject | `with gold as (select * from bronze.secom_runs) select * from gold` |
| bad11 | reject | reject | reject | `select * from gold.dim_wafer union select run_id, null, null, null from bronze.secom_runs` |
| bad12 | reject | reject | allow | `select current_setting('home_directory')` |
| bad13 | reject | reject | reject | `select * from glob('data/raw/*')` |
| bad14 | reject | reject | reject | `select * from silver.int_sensor_stats` |
| bad15 | reject | reject | reject | `select * from information_schema.tables` |
| bad16 | reject | reject | reject | `select * from duckdb_settings()` |
| bad17 | reject | reject | allow | `select read_text('README.md')` |
| bad18 | reject | reject | reject | `pragma show_tables` |
| bad19 | reject | reject | reject | `select * from gold.dim_wafer /* ; */ cross join bronze.context_tools` |
| bad20 | reject | reject | reject | `attach 'other.duckdb' as o` |
