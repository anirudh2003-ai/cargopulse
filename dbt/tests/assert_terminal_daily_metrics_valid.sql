select
    'occupancy_interval' as error_source,
    interval_start::text as error_key

from {{ ref('lng_terminal_occupancy_intervals') }}

where
    interval_end <= interval_start
    or duration_minutes <= 0
    or occupied_berths < 0
    or occupied_berths > 3
    or active_calls < 0

union all

select
    'daily_metric' as error_source,
    metric_date::text as error_key

from {{ ref('lng_terminal_daily_metrics') }}

where
    arrivals < 0
    or departures < 0
    or occupied_berth_minutes < 0
    or max_occupied_berths < 0
    or max_occupied_berths > 3
    or terminal_utilisation_pct < 0
    or terminal_utilisation_pct > 100
    or mean_occupied_berths < 0
    or mean_occupied_berths > 3
    or severe_delay_arrivals < 0
