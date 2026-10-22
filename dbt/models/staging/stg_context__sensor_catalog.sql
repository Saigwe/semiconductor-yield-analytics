select
    cast(sensor_id as integer)  as sensor_id,
    cast(step_id as integer)    as step_id,
    tool_id,
    parameter_name,
    unit
from {{ source('bronze', 'context_sensor_catalog') }}
