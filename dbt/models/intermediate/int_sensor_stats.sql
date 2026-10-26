-- Grain: one row per sensor. Control limits for scoring, and usability flags.
-- mean_value / stddev_value come from the reference period's passing wafers only (see int_runs), so a wafer's
-- z-score never uses readings from wafers tested after it. Missing rate describes the whole dataset.
with readings as (
    select r.*, u.is_reference_period and not u.is_fail as is_reference_reading
    from {{ ref('stg_secom__sensor_readings') }} r
    join {{ ref('int_runs') }} u on r.run_id = u.run_id
)

select
    sensor_id,
    count(*)                                                                        as n_runs,
    sum(case when is_missing then 1 else 0 end)                                     as n_missing,
    avg(case when is_missing then 1.0 else 0.0 end)                                 as missing_rate,
    count(case when is_reference_reading and not is_missing then 1 end)             as n_reference,
    avg(case when is_reference_reading then reading_value end)                      as mean_value,
    stddev_samp(case when is_reference_reading then reading_value end)              as stddev_value,
    min(reading_value)                                                              as min_value,
    max(reading_value)                                                              as max_value,
    coalesce(stddev_samp(case when is_reference_reading then reading_value end), 0) = 0 as is_constant,
    avg(case when is_missing then 1.0 else 0.0 end) > 0.5                           as is_mostly_missing
from readings
group by sensor_id
