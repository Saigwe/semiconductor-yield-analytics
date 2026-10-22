-- Grain: one row per usable sensor. Univariate screen: standardised mean difference (Cohen's d) between
-- failing and passing wafers. A ranking aid for engineers, not a causal claim.
with by_class as (
    select
        f.sensor_id,
        avg(case when w.is_fail then f.reading_value end)                   as mean_fail,
        avg(case when not w.is_fail then f.reading_value end)               as mean_pass,
        stddev_samp(case when w.is_fail then f.reading_value end)           as sd_fail,
        stddev_samp(case when not w.is_fail then f.reading_value end)       as sd_pass,
        count(case when w.is_fail and not f.is_missing then 1 end)          as n_fail,
        count(case when not w.is_fail and not f.is_missing then 1 end)      as n_pass
    from {{ ref('fct_sensor_reading') }} f
    join {{ ref('fct_wafer_test') }} w on f.run_id = w.run_id
    group by f.sensor_id
),

effect as (
    select
        b.*,
        sqrt(
            ((n_fail - 1) * sd_fail * sd_fail + (n_pass - 1) * sd_pass * sd_pass)
            / nullif(n_fail + n_pass - 2, 0)
        ) as pooled_sd
    from by_class b
    where n_fail >= 2 and n_pass >= 2
),

scored as (
    select
        e.*,
        (e.mean_fail - e.mean_pass) / nullif(e.pooled_sd, 0) as effect_size
    from effect e
)

select
    s.sensor_id,
    d.parameter_name,
    d.step_name,
    d.tool_id,
    s.n_fail,
    s.n_pass,
    s.mean_fail,
    s.mean_pass,
    s.effect_size,
    abs(s.effect_size)                                          as abs_effect_size,
    rank() over (order by abs(s.effect_size) desc nulls last)   as signal_rank
from scored s
join {{ ref('dim_sensor') }} d on s.sensor_id = d.sensor_id
where d.is_usable
