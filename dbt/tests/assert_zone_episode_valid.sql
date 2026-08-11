select *

from {{ ref('int_ais_zone_episodes') }}

where
    episode_end < episode_start
    or duration_minutes < 0
    or point_count <= 0
