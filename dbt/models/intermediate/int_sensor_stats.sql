-- Grain: one row per sensor. Baseline statistics used for scoring and for flagging unusable sensors.
with readings as (
    select * from {{ ref('stg_secom__sensor_readings') }}
)

select
    sensor_id,
    count(*)                                                    as n_runs,
    sum(case when is_missing then 1 else 0 end)                 as n_missing,
    avg(case when is_missing then 1.0 else 0.0 end)             as missing_rate,
    avg(reading_value)                                          as mean_value,
    stddev_samp(reading_value)                                  as stddev_value,
    min(reading_value)                                          as min_value,
    max(reading_value)                                          as max_value,
    coalesce(stddev_samp(reading_value), 0) = 0                 as is_constant,
    avg(case when is_missing then 1.0 else 0.0 end) > 0.5       as is_mostly_missing
from readings
group by sensor_id
