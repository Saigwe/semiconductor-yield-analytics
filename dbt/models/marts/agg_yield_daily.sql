-- Grain: one row per test date. THE yield definition: passed wafers / tested wafers. Do not recompute in BI.
select
    test_date,
    count(*)                                        as wafers_tested,
    sum(case when is_fail then 1 else 0 end)        as wafers_failed,
    sum(case when is_fail then 0 else 1 end)        as wafers_passed,
    cast(sum(case when is_fail then 0 else 1 end) as double) / count(*) as yield_rate
from {{ ref('fct_wafer_test') }}
group by test_date
