-- Grain: one row per lot. Same yield definition as agg_yield_daily.
select
    lot_id,
    count(*)                                        as wafers_tested,
    sum(case when is_fail then 1 else 0 end)        as wafers_failed,
    sum(case when is_fail then 0 else 1 end)        as wafers_passed,
    cast(sum(case when is_fail then 0 else 1 end) as double) / count(*) as yield_rate
from {{ ref('fct_wafer_test') }}
group by lot_id
