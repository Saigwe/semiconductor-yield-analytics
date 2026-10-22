-- Grain: one row per wafer test run x sensor.
-- On Databricks, switch to incremental + liquid clustering on (test_date, sensor_id); see docs/layer_plan.md.
select
    s.run_id,
    w.wafer_id,
    s.sensor_id,
    r.test_date,
    s.reading_value,
    s.is_missing,
    s.z_score,
    s.is_out_of_control
from {{ ref('int_readings_scored') }} s
join {{ ref('stg_secom__runs') }} r on s.run_id = r.run_id
join {{ ref('dim_wafer') }} w on s.run_id = w.run_id
