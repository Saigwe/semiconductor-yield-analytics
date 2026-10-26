-- Grain: one row per run. Time order and the SPC reference period (Phase I), defined once.
-- The reference period is the first var('reference_frac', 0.5) of runs by test time. Control limits come only from
-- PASSING wafers inside it, so later wafers are judged against limits set before they were tested.
with runs as (
    select
        run_id,
        is_fail,
        run_ts,
        row_number() over (order by run_ts, run_id) as run_seq,
        count(*) over ()                            as n_runs
    from {{ ref('stg_secom__runs') }}
)

select
    run_id,
    run_seq,
    run_ts,
    is_fail,
    run_seq <= ceil(n_runs * {{ var('reference_frac', 0.5) }}) as is_reference_period
from runs
