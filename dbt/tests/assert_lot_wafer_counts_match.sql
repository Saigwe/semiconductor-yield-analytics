select l.lot_id, l.n_wafers, a.wafers_tested
from {{ ref('dim_lot') }} l
join {{ ref('agg_yield_by_lot') }} a on l.lot_id = a.lot_id
where l.n_wafers <> a.wafers_tested
