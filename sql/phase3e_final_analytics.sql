-- ============================================================
-- CargoPulse Phase 3E
-- Final call-level analytics output
-- ============================================================


DROP MATERIALIZED VIEW IF EXISTS
    public.lng_call_analytics;


CREATE MATERIALIZED VIEW
public.lng_call_analytics
AS


SELECT

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
        AS arrival_metric_date,

    daily.arrivals
        AS arrival_day_terminal_arrivals,

    daily.departures
        AS arrival_day_terminal_departures,

    daily.max_occupied_berths
        AS arrival_day_max_occupied_berths,

    daily.terminal_utilisation_pct
        AS arrival_day_terminal_utilisation_pct,

    daily.mean_occupied_berths
        AS arrival_day_mean_occupied_berths


FROM public.lng_call_delay_metrics AS calls

LEFT JOIN public.lng_terminal_daily_metrics AS daily

    ON daily.metric_date
       = calls.berth_arrival_time::date;


CREATE UNIQUE INDEX
idx_lng_call_analytics_id

ON public.lng_call_analytics (
    validated_call_id
);


CREATE INDEX
idx_lng_call_analytics_delay

ON public.lng_call_analytics (
    delay_band
);


ANALYZE public.lng_call_analytics;
