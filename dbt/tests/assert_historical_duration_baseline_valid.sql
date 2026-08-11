select
    metric_date,
    berth_zone_code

from {{ ref('lng_historical_duration_baseline_daily') }}

where
    berth_history_calls < 0

    or terminal_history_calls < 0

    or (
        baseline_scope = 'insufficient_history'
        and (
            expected_minutes is not null
            or p75_minutes is not null
            or p90_minutes is not null
            or p95_minutes is not null
        )
    )

    or (
        baseline_scope <> 'insufficient_history'
        and (
            expected_minutes is null
            or p75_minutes is null
            or p90_minutes is null
            or p95_minutes is null
        )
    )

    or (
        expected_minutes is not null
        and (
            expected_minutes > p75_minutes
            or p75_minutes > p90_minutes
            or p90_minutes > p95_minutes
        )
    )

group by
    metric_date,
    berth_zone_code

having count(*) > 1

union all

select
    metric_date,
    berth_zone_code

from {{ ref('lng_historical_duration_baseline_daily') }}

where
    berth_history_calls < 0
    or terminal_history_calls < 0
    or (
        baseline_scope = 'insufficient_history'
        and expected_minutes is not null
    )
    or (
        baseline_scope <> 'insufficient_history'
        and expected_minutes is null
    )
    or (
        expected_minutes is not null
        and (
            expected_minutes > p75_minutes
            or p75_minutes > p90_minutes
            or p90_minutes > p95_minutes
        )
    )
