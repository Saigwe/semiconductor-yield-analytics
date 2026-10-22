-- Grain: one row per wafer test run.
with reading_counts as (
    select
        run_id,
        count(*)                                                as n_readings,
        sum(case when is_missing then 1 else 0 end)             as n_missing_readings,
        sum(case when is_out_of_control then 1 else 0 end)      as n_out_of_control
    from {{ ref('int_readings_scored') }}
    group by run_id
)

select
    r.run_id,
    w.wafer_id,
    w.lot_id,
    r.run_ts,
    r.test_date,
    r.is_fail,
    coalesce(c.n_readings, 0)          as n_readings,
    coalesce(c.n_missing_readings, 0)  as n_missing_readings,
    coalesce(c.n_out_of_control, 0)    as n_out_of_control
from {{ ref('stg_secom__runs') }} r
join {{ ref('dim_wafer') }} w on r.run_id = w.run_id
left join reading_counts c on r.run_id = c.run_id
