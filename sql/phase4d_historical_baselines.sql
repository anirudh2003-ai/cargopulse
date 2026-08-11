-- ============================================================
-- CargoPulse Phase 4D
-- Historical expanding duration baselines
--
-- For each calendar day, use ONLY calls completed before
-- that day.
-- ============================================================


DROP MATERIALIZED VIEW IF EXISTS
    public.lng_historical_duration_baseline_daily;


CREATE MATERIALIZED VIEW
public.lng_historical_duration_baseline_daily
AS


WITH days AS (

    SELECT metric_date

    FROM public.lng_terminal_daily_metrics
),


eligible_completed_calls AS (

    SELECT
        validated_call_id,
        berth_zone_code,
        berth_departure_time,
        berth_duration_minutes

    FROM public.lng_call_operations

    WHERE
        berth_detection_confidence = 'high'

        AND berth_continuity <> 'review'

        AND movement_coverage = 'full'
),


berth_history AS (

    SELECT

        days.metric_date,

        calls.berth_zone_code,

        COUNT(calls.validated_call_id)
            AS berth_history_calls,

        percentile_cont(0.50)
        WITHIN GROUP (
            ORDER BY calls.berth_duration_minutes
        ) AS berth_median_minutes,

        percentile_cont(0.75)
        WITHIN GROUP (
            ORDER BY calls.berth_duration_minutes
        ) AS berth_p75_minutes,

        percentile_cont(0.90)
        WITHIN GROUP (
            ORDER BY calls.berth_duration_minutes
        ) AS berth_p90_minutes,

        percentile_cont(0.95)
        WITHIN GROUP (
            ORDER BY calls.berth_duration_minutes
        ) AS berth_p95_minutes


    FROM days

    LEFT JOIN eligible_completed_calls AS calls

        ON calls.berth_departure_time
            < days.metric_date::timestamp

    GROUP BY
        days.metric_date,
        calls.berth_zone_code
),


terminal_history AS (

    SELECT

        days.metric_date,

        COUNT(calls.validated_call_id)
            AS terminal_history_calls,

        percentile_cont(0.50)
        WITHIN GROUP (
            ORDER BY calls.berth_duration_minutes
        ) AS terminal_median_minutes,

        percentile_cont(0.75)
        WITHIN GROUP (
            ORDER BY calls.berth_duration_minutes
        ) AS terminal_p75_minutes,

        percentile_cont(0.90)
        WITHIN GROUP (
            ORDER BY calls.berth_duration_minutes
        ) AS terminal_p90_minutes,

        percentile_cont(0.95)
        WITHIN GROUP (
            ORDER BY calls.berth_duration_minutes
        ) AS terminal_p95_minutes


    FROM days

    LEFT JOIN eligible_completed_calls AS calls

        ON calls.berth_departure_time
            < days.metric_date::timestamp

    GROUP BY days.metric_date
)


SELECT

    days.metric_date,

    zones.berth_zone_code,

    COALESCE(
        berth.berth_history_calls,
        0
    ) AS berth_history_calls,

    terminal.terminal_history_calls,


    CASE

        WHEN berth.berth_history_calls >= 5
            THEN 'historical_berth'

        WHEN terminal.terminal_history_calls >= 5
            THEN 'historical_terminal'

        ELSE 'insufficient_history'

    END AS baseline_scope,


    CASE

        WHEN berth.berth_history_calls >= 5
            THEN berth.berth_median_minutes

        WHEN terminal.terminal_history_calls >= 5
            THEN terminal.terminal_median_minutes

        ELSE NULL

    END AS expected_minutes,


    CASE

        WHEN berth.berth_history_calls >= 5
            THEN berth.berth_p75_minutes

        WHEN terminal.terminal_history_calls >= 5
            THEN terminal.terminal_p75_minutes

        ELSE NULL

    END AS p75_minutes,


    CASE

        WHEN berth.berth_history_calls >= 5
            THEN berth.berth_p90_minutes

        WHEN terminal.terminal_history_calls >= 5
            THEN terminal.terminal_p90_minutes

        ELSE NULL

    END AS p90_minutes,


    CASE

        WHEN berth.berth_history_calls >= 5
            THEN berth.berth_p95_minutes

        WHEN terminal.terminal_history_calls >= 5
            THEN terminal.terminal_p95_minutes

        ELSE NULL

    END AS p95_minutes


FROM days


CROSS JOIN (

    SELECT DISTINCT
        berth_zone_code

    FROM public.lng_call_operations

) AS zones


LEFT JOIN berth_history AS berth

    ON berth.metric_date
       = days.metric_date

    AND berth.berth_zone_code
        = zones.berth_zone_code


JOIN terminal_history AS terminal

    ON terminal.metric_date
       = days.metric_date;


CREATE UNIQUE INDEX
idx_historical_duration_baseline_daily

ON public.lng_historical_duration_baseline_daily (
    metric_date,
    berth_zone_code
);


ANALYZE public.lng_historical_duration_baseline_daily;
