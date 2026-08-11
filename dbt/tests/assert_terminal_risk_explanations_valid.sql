select
    metric_date

from {{ ref('lng_terminal_risk_explanations_daily') }}

where
    risk_score < 0
    or risk_score > 100

    or (
        risk_trend = 'initial'
        and risk_change_1d is not null
    )

    or (
        risk_trend = 'rising_fast'
        and risk_change_1d < 10
    )

    or (
        risk_trend = 'rising'
        and (
            risk_change_1d < 3
            or risk_change_1d >= 10
        )
    )

    or (
        risk_trend = 'falling_fast'
        and risk_change_1d > -10
    )

    or (
        risk_trend = 'falling'
        and (
            risk_change_1d > -3
            or risk_change_1d <= -10
        )
    )

    or (
        risk_trend = 'stable'
        and (
            risk_change_1d >= 3
            or risk_change_1d <= -3
        )
    )

    or primary_driver_points < 0
    or secondary_driver_points < 0
    or tertiary_driver_points < 0

    or (
        secondary_driver_points is not null
        and primary_driver_points < secondary_driver_points
    )

    or (
        tertiary_driver_points is not null
        and secondary_driver_points < tertiary_driver_points
    )
