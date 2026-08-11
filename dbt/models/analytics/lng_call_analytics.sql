{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 3E
-- Final call-level analytics output
-- ============================================================

select

    calls.validated_call_id,

    calls.mmsi,
    calls.imo,
    calls.vessel_name,

    calls.terminal_id,
    calls.berth_zone_code,

    calls.berth_arrival_time,
    calls.berth_departure_time,

    calls.berth_duration_minutes,

    calls.expected_duration_minutes,

    calls.duration_variance_minutes,

    calls.estimated_delay_minutes,
    calls.estimated_delay_hours,

    calls.delay_band,
    calls.delay_quality,

    calls.baseline_scope,
    calls.baseline_sample_size,

    calls.berth_detection_confidence,
    calls.berth_continuity,

    calls.movement_coverage,

    calls.inbound_transit_minutes,
    calls.outbound_transit_minutes,

    daily.metric_date
        as arrival_metric_date,

    daily.arrivals
        as arrival_day_terminal_arrivals,

    daily.departures
        as arrival_day_terminal_departures,

    daily.max_occupied_berths
        as arrival_day_max_occupied_berths,

    daily.terminal_utilisation_pct
        as arrival_day_terminal_utilisation_pct,

    daily.mean_occupied_berths
        as arrival_day_mean_occupied_berths

from {{ ref('lng_call_delay_metrics') }} as calls

left join {{ ref('lng_terminal_daily_metrics') }} as daily

    on daily.metric_date
       = calls.berth_arrival_time::date
