select run_id, run_ts
from {{ ref('stg_secom__runs') }}
where run_ts > _loaded_at
