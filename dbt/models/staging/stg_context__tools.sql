select
    tool_id,
    tool_type,
    cast(step_id as integer)        as step_id,
    cast(chamber_count as integer)  as chamber_count
from {{ source('bronze', 'context_tools') }}
