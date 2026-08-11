select
    metric_date

from {{ ref('lng_terminal_risk_features_daily') }}

where
    arrivals < 0
    or departures < 0

    or terminal_utilisation_pct < 0
    or terminal_utilisation_pct > 100

    or capacity_pressure < 0
    or capacity_pressure > 1

    or berth_saturation < 0
    or berth_saturation > 1

    or active_calls < 0
    or active_scored_calls < 0
    or active_unscored_calls < 0
    or active_delayed_calls < 0
    or active_severe_calls < 0

    or active_scored_calls > active_calls
    or active_unscored_calls > active_calls

    or active_delayed_calls > active_scored_calls
    or active_severe_calls > active_scored_calls
    or active_severe_calls > active_delayed_calls

    or active_delay_share < 0
    or active_delay_share > 1

    or active_severe_share < 0
    or active_severe_share > 1

    or unscored_active_share < 0
    or unscored_active_share > 1

    or delayed_departures < 0
    or severe_departures < 0

    or arrivals_3d < 0
    or departures_3d < 0

    or severe_departures_3d < 0

    or positive_vessel_balance_3d < 0
