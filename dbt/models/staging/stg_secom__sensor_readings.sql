select
    cast(run_id as integer)          as run_id,
    cast(sensor_id as integer)       as sensor_id,
    cast(reading_value as double)    as reading_value,
    reading_value is null            as is_missing
from {{ source('bronze', 'secom_sensor_readings') }}
