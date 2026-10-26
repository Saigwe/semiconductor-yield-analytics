-- Grain: one row per test date. A p-chart of the daily fail rate (Shewhart, 3-sigma), with the centre line set from
-- the reference period. Limits widen on days with few wafers, so a bad day with 3 wafers isn't over-read.
with reference as (
    select avg(case when is_fail then 1.0 else 0.0 end) as p_bar
    from {{ ref('int_runs') }}
    where is_reference_period
),

daily as (
    select
        d.test_date,
        d.wafers_tested,
        d.wafers_failed,
        1 - d.yield_rate as fail_rate,
        bool_and(u.is_reference_period) as is_reference_period
    from {{ ref('agg_yield_daily') }} d
    join {{ ref('fct_wafer_test') }} w on w.test_date = d.test_date
    join {{ ref('int_runs') }} u on u.run_id = w.run_id
    group by d.test_date, d.wafers_tested, d.wafers_failed, d.yield_rate
)

select
    d.test_date,
    d.wafers_tested,
    d.wafers_failed,
    d.fail_rate,
    r.p_bar                                                                        as centre_line,
    least(1.0, r.p_bar + 3 * sqrt(r.p_bar * (1 - r.p_bar) / d.wafers_tested))      as upper_limit,
    greatest(0.0, r.p_bar - 3 * sqrt(r.p_bar * (1 - r.p_bar) / d.wafers_tested))   as lower_limit,
    d.fail_rate > r.p_bar + 3 * sqrt(r.p_bar * (1 - r.p_bar) / d.wafers_tested)    as is_above_limit,
    d.is_reference_period
from daily d
cross join reference r
