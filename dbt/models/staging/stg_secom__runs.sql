select
    cast(run_id as integer)                         as run_id,
    cast(label_raw as integer)                      as label_raw,
    label_raw = 1                                   as is_fail,
    {{ parse_run_ts('run_ts_raw') }}                as run_ts,
    cast({{ parse_run_ts('run_ts_raw') }} as date)  as test_date,
    _loaded_at
from {{ source('bronze', 'secom_runs') }}
