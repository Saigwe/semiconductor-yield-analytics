select * from {{ ref('agg_yield_by_lot') }}
where wafers_failed > wafers_tested
   or wafers_passed + wafers_failed <> wafers_tested
