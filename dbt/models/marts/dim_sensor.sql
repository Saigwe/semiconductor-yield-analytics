-- Grain: one row per sensor. Usability flags are exposed (not filtered) so consumers can see why a sensor is excluded.
select
    c.sensor_id,
    c.parameter_name,
    c.unit,
    c.step_id,
    p.step_name,
    c.tool_id,
    s.missing_rate,
    s.mean_value,
    s.stddev_value,
    s.is_constant,
    s.is_mostly_missing,
    not (s.is_constant or s.is_mostly_missing) as is_usable
from {{ ref('stg_context__sensor_catalog') }} c
join {{ ref('stg_context__process_steps') }} p on c.step_id = p.step_id
join {{ ref('int_sensor_stats') }} s on c.sensor_id = s.sensor_id
