select
    metric_date

from {{ ref('lng_terminal_risk_score_daily') }}

where
    risk_score < 0
    or risk_score > 100

    or capacity_points < 0
    or capacity_points > 20

    or saturation_points < 0
    or saturation_points > 10

    or active_delay_points < 0
    or active_delay_points > 20

    or active_severe_points < 0
    or active_severe_points > 15

    or delay_intensity_points < 0
    or delay_intensity_points > 10

    or utilisation_3d_points < 0
    or utilisation_3d_points > 15

    or backlog_points < 0
    or backlog_points > 10

    or data_coverage_score < 0
    or data_coverage_score > 1
