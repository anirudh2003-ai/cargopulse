-- ============================================================
-- CargoPulse Phase 3C
-- Berth performance and utilisation
-- ============================================================


DROP MATERIALIZED VIEW IF EXISTS
    public.lng_berth_performance;


CREATE MATERIALIZED VIEW
public.lng_berth_performance
AS


WITH bounds AS (

    SELECT
        MIN(recorded_at) AS dataset_start,
        MAX(recorded_at) AS dataset_end,

        EXTRACT(
            EPOCH FROM (
                MAX(recorded_at)
                - MIN(recorded_at)
            )
        ) / 60.0 AS dataset_minutes

    FROM public.ais_positions
),


clipped_calls AS (

    SELECT

        calls.berth_zone_code,

        GREATEST(
            calls.berth_arrival_time,
            bounds.dataset_start
        ) AS occupied_start,

        LEAST(
            calls.berth_departure_time,
            bounds.dataset_end
        ) AS occupied_end

    FROM public.lng_call_operations AS calls

    CROSS JOIN bounds

    WHERE
        calls.berth_arrival_time IS NOT NULL
        AND calls.berth_departure_time IS NOT NULL
),


events_raw AS (

    SELECT
        berth_zone_code,
        occupied_start AS event_time,
        1 AS delta

    FROM clipped_calls

    WHERE occupied_end > occupied_start


    UNION ALL


    SELECT
        berth_zone_code,
        occupied_end AS event_time,
        -1 AS delta

    FROM clipped_calls

    WHERE occupied_end > occupied_start
),


events AS (

    SELECT
        berth_zone_code,
        event_time,
        SUM(delta) AS delta

    FROM events_raw

    GROUP BY
        berth_zone_code,
        event_time
),


occupancy_running AS (

    SELECT

        berth_zone_code,
        event_time,

        SUM(delta) OVER (
            PARTITION BY berth_zone_code
            ORDER BY event_time
            ROWS BETWEEN
                UNBOUNDED PRECEDING
                AND CURRENT ROW
        ) AS occupancy_count,

        LEAD(event_time) OVER (
            PARTITION BY berth_zone_code
            ORDER BY event_time
        ) AS next_event_time

    FROM events
),


occupancy_summary AS (

    SELECT

        berth_zone_code,

        SUM(
            CASE

                WHEN occupancy_count > 0
                 AND next_event_time IS NOT NULL

                THEN EXTRACT(
                    EPOCH FROM (
                        next_event_time - event_time
                    )
                ) / 60.0

                ELSE 0

            END
        ) AS occupied_minutes

    FROM occupancy_running

    GROUP BY berth_zone_code
),


call_summary AS (

    SELECT

        berth_zone_code,

        COUNT(*) AS total_calls,

        COUNT(*) FILTER (
            WHERE delay_band <> 'unscored'
        ) AS scored_calls,

        COUNT(*) FILTER (
            WHERE delay_band = 'elevated'
        ) AS elevated_calls,

        COUNT(*) FILTER (
            WHERE delay_band = 'high'
        ) AS high_delay_calls,

        COUNT(*) FILTER (
            WHERE delay_band = 'severe'
        ) AS severe_delay_calls,

        percentile_cont(0.50)
        WITHIN GROUP (
            ORDER BY berth_duration_minutes
        ) AS median_duration_minutes,

        percentile_cont(0.90)
        WITHIN GROUP (
            ORDER BY berth_duration_minutes
        ) AS p90_duration_minutes,

        AVG(
            estimated_delay_minutes
        ) FILTER (
            WHERE delay_band <> 'unscored'
        ) AS mean_estimated_delay_minutes

    FROM public.lng_call_delay_metrics

    GROUP BY berth_zone_code
)


SELECT

    summary.berth_zone_code,

    summary.total_calls,
    summary.scored_calls,

    summary.elevated_calls,
    summary.high_delay_calls,
    summary.severe_delay_calls,

    summary.median_duration_minutes,
    summary.p90_duration_minutes,

    summary.mean_estimated_delay_minutes,

    occupancy.occupied_minutes,

    (
        occupancy.occupied_minutes
        / bounds.dataset_minutes
        * 100.0
    ) AS utilisation_pct


FROM call_summary AS summary

JOIN occupancy_summary AS occupancy
    ON occupancy.berth_zone_code
       = summary.berth_zone_code

CROSS JOIN bounds;


CREATE UNIQUE INDEX
idx_lng_berth_performance

ON public.lng_berth_performance (
    berth_zone_code
);
