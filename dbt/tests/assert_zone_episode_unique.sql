select
    mmsi,
    episode_number,
    count(*) as row_count

from {{ ref('int_ais_zone_episodes') }}

group by
    mmsi,
    episode_number

having count(*) > 1
