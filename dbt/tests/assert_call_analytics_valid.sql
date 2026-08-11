select *

from {{ ref('lng_call_analytics') }}

where
    berth_departure_time < berth_arrival_time

    or berth_duration_minutes < 0

    or estimated_delay_minutes < 0

    or estimated_delay_hours < 0

    or arrival_day_terminal_arrivals < 0

    or arrival_day_terminal_departures < 0

    or arrival_day_max_occupied_berths < 0

    or arrival_day_max_occupied_berths > 3

    or arrival_day_terminal_utilisation_pct < 0

    or arrival_day_terminal_utilisation_pct > 100

    or arrival_day_mean_occupied_berths < 0

    or arrival_day_mean_occupied_berths > 3
