select *

from {{ ref('lng_berth_performance') }}

where
    total_calls <= 0

    or scored_calls < 0

    or scored_calls > total_calls

    or elevated_calls < 0

    or high_delay_calls < 0

    or severe_delay_calls < 0

    or occupied_minutes < 0

    or utilisation_pct < 0

    or utilisation_pct > 100

    or median_duration_minutes < 0

    or p90_duration_minutes < median_duration_minutes

    or mean_estimated_delay_minutes < 0
