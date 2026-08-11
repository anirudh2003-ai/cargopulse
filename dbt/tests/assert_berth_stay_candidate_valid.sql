select *

from {{ ref('int_lng_berth_stay_candidates') }}

where
    berth_end < berth_start

    or duration_minutes < 0

    or point_count <= 0

    or stationary_fraction < 0

    or stationary_fraction > 1
