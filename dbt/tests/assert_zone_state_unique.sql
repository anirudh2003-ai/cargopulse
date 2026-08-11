select
    mmsi,
    recorded_at,
    count(*) as row_count

from {{ ref('int_ais_position_zone_state') }}

group by
    mmsi,
    recorded_at

having count(*) > 1
