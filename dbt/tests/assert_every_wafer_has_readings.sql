select run_id from {{ ref('fct_wafer_test') }}
where n_readings = 0
