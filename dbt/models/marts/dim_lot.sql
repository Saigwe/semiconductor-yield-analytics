-- Grain: one row per lot.
select
    m.lot_id,
    count(*)        as n_wafers,
    min(r.run_ts)   as first_test_ts,
    max(r.run_ts)   as last_test_ts
from {{ ref('stg_context__lot_wafer_map') }} m
join {{ ref('stg_secom__runs') }} r on m.run_id = r.run_id
group by m.lot_id
