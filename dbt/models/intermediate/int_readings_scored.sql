-- Grain: one row per run x sensor. Shewhart-style z-score against the sensor's own baseline.
-- z is NULL (not 0) when the reading is missing or the sensor is constant: unknown must not look in control.
with readings as (
    select * from {{ ref('stg_secom__sensor_readings') }}
),

stats as (
    select * from {{ ref('int_sensor_stats') }}
)

select
    r.run_id,
    r.sensor_id,
    r.reading_value,
    r.is_missing,
    case
        when r.is_missing or s.is_constant then null
        else (r.reading_value - s.mean_value) / s.stddev_value
    end as z_score,
    case
        when r.is_missing or s.is_constant then null
        else abs((r.reading_value - s.mean_value) / s.stddev_value) > {{ var('ooc_z_threshold', 3) }}
    end as is_out_of_control
from readings r
join stats s on r.sensor_id = s.sensor_id
