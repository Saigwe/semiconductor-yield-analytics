select step_id, step_name, step_seq
from {{ ref('stg_context__process_steps') }}
