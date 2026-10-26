-- Control limits must bracket the centre line, and stay within [0, 1].
select test_date, lower_limit, centre_line, upper_limit
from {{ ref('rpt_yield_p_chart') }}
where not (0 <= lower_limit and lower_limit <= centre_line and centre_line <= upper_limit and upper_limit <= 1)
