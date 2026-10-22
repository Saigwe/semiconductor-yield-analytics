-- Grain: one row per wafer. In SECOM each run is one wafer test, so run_id is carried as the natural key.
select wafer_id, run_id, lot_id, slot_no
from {{ ref('stg_context__lot_wafer_map') }}
