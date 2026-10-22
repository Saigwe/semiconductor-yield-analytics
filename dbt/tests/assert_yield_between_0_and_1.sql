select 'daily' as source, cast(test_date as varchar(10)) as k, yield_rate
from {{ ref('agg_yield_daily') }}
where yield_rate < 0 or yield_rate > 1
union all
select 'lot' as source, lot_id as k, yield_rate
from {{ ref('agg_yield_by_lot') }}
where yield_rate < 0 or yield_rate > 1
