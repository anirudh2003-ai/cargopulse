select *

from {{ ref('lng_call_delay_metrics') }}

where
    estimated_delay_minutes < 0

    or estimated_delay_hours < 0

    or baseline_sample_size <= 0

    or expected_duration_minutes <= 0

    or p75_minutes < expected_duration_minutes

    or p90_minutes < p75_minutes

    or p95_minutes < p90_minutes

    or (
        delay_quality in (
            'censored',
            'review',
            'lower_confidence'
        )
        and delay_band <> 'unscored'
    )

    or (
        delay_quality in (
            'usable',
            'usable_with_gap'
        )
        and delay_band = 'unscored'
    )
