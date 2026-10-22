select
    t.tool_id,
    t.tool_type,
    t.step_id,
    p.step_name,
    t.chamber_count
from {{ ref('stg_context__tools') }} t
join {{ ref('stg_context__process_steps') }} p on t.step_id = p.step_id
