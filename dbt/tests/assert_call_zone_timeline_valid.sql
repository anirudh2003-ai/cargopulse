select *

from {{ ref('int_lng_call_zone_timeline') }}

where
    episode_end < episode_start

    or duration_minutes < 0

    or point_count <= 0

    or movement_phase not in (
        'inbound',
        'berth',
        'berth_transition',
        'outbound'
    )
