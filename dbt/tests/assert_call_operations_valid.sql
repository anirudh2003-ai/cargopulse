select *

from {{ ref('int_lng_call_operations') }}

where
    berth_departure_time < berth_arrival_time

    or berth_duration_minutes < 0

    or observed_berth_minutes < 0

    or bridged_minutes < 0

    or berth_point_count <= 0

    or fragment_count <= 0

    or stationary_fraction not between 0 and 1

    or movement_coverage not in (
        'full',
        'inbound_only',
        'outbound_only',
        'berth_only'
    )
