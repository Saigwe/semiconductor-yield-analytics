select
    cast(run_id as integer)   as run_id,
    wafer_id,
    lot_id,
    cast(slot_no as integer)  as slot_no
from {{ source('bronze', 'context_lot_wafer_map') }}
