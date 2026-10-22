select
    cast(step_id as integer)   as step_id,
    step_name,
    cast(step_seq as integer)  as step_seq
from {{ source('bronze', 'context_process_steps') }}
