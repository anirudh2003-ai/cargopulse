select *

from {{ ref('int_lng_operational_calls') }}

where

    (
        berth_arrival_time is not null
        and berth_departure_time < berth_arrival_time
    )

    or (
        berth_duration_minutes is not null
        and berth_duration_minutes < 0
    )

    or (
        bridged_minutes is not null
        and bridged_minutes < 0
    )

    or (
        berth_point_count is not null
        and berth_point_count <= 0
    )

    or (
        fragment_count is not null
        and fragment_count <= 0
    )

    or (
        stationary_fraction is not null
        and stationary_fraction not between 0 and 1
    )

    or (
        berth_detection_confidence is not null
        and berth_detection_confidence not in (
            'high',
            'medium',
            'low'
        )
    )

    or (
        berth_continuity is not null
        and berth_continuity not in (
            'continuous',
            'minor_gaps',
            'moderate_gap',
            'review'
        )
    )
