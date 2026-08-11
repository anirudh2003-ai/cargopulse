-- ============================================================
-- CargoPulse Phase 4A
-- Leakage-safe daily supply-risk features
-- ============================================================
--
-- IMPORTANT:
--
-- Active vessel delay status is calculated using elapsed berth
-- time AS OF THAT DAY.
--
-- We do NOT use the vessel's eventual final delay_band while
-- looking at an earlier day.
-- ============================================================


DROP MATERIALIZED VIEW IF EXISTS
    public.lng_terminal_risk_features_daily;


CREATE MATERIALIZED VIEW
public.lng_terminal_risk_features_daily
AS


-- ============================================================
-- 1. Daily terminal metrics
-- ============================================================

WITH daily AS (

    SELECT
        metric_date,

        arrivals,
        departures,

        terminal_utilisation_pct,
        mean_occupied_berths,
        max_occupied_berths

    FROM public.lng_terminal_daily_metrics
),


-- ============================================================
-- 2. Dataset boundary
-- ============================================================

dataset_bounds AS (

    SELECT
        MIN(recorded_at) AS dataset_start,
        MAX(recorded_at) AS dataset_end

    FROM public.ais_positions
),


-- ============================================================
-- 3. Attach historical duration baseline to every call
-- ============================================================

call_baselines AS (

    SELECT

        daily.metric_date,

        calls.validated_call_id,
        calls.mmsi,
        calls.imo,
        calls.vessel_name,

        calls.terminal_id,
        calls.berth_zone_code,

        calls.berth_arrival_time,
        calls.berth_departure_time,

        calls.berth_detection_confidence,
        calls.berth_continuity,

        bounds.dataset_start,
        bounds.dataset_end,

        historical.baseline_scope,

        historical.expected_minutes,

        historical.p75_minutes,

        historical.p90_minutes,

        historical.p95_minutes,


        (
            calls.berth_arrival_time
            <= bounds.dataset_start
               + INTERVAL '10 minutes'
        ) AS left_censored


    FROM daily


    JOIN public.lng_call_operations
        AS calls

        ON calls.berth_arrival_time
            < daily.metric_date::timestamp
              + INTERVAL '1 day'

        AND calls.berth_departure_time
            > daily.metric_date::timestamp


    LEFT JOIN
        public.lng_historical_duration_baseline_daily
        AS historical

        ON historical.metric_date
           = daily.metric_date

        AND historical.berth_zone_code
            = calls.berth_zone_code


    CROSS JOIN dataset_bounds
        AS bounds
),


-- ============================================================
-- 4. One row for every call that overlaps every calendar day
-- ============================================================

active_call_day AS (

    SELECT

        metric_date,

        validated_call_id,

        berth_zone_code,

        berth_arrival_time,
        berth_departure_time,

        berth_detection_confidence,
        berth_continuity,

        left_censored,

        baseline_scope,

        expected_minutes,
        p75_minutes,
        p90_minutes,
        p95_minutes,


        GREATEST(

            EXTRACT(

                EPOCH FROM (

                    LEAST(
                        berth_departure_time,

                        metric_date::timestamp
                            + INTERVAL '1 day'
                    )

                    -

                    berth_arrival_time

                )

            ) / 60.0,

            0

        ) AS elapsed_minutes_as_of_day


    FROM call_baselines
),


-- ============================================================
-- 5. Daily active-call features
-- ============================================================

active_summary AS (

    SELECT

        metric_date,


        COUNT(*)
            AS active_calls,


        -- ====================================================
        -- Scorable active calls
        -- ====================================================

        COUNT(*) FILTER (

            WHERE
                NOT left_censored

                AND berth_detection_confidence = 'high'

                AND berth_continuity <> 'review'

                AND baseline_scope
                    <> 'insufficient_history'

                AND expected_minutes IS NOT NULL

        ) AS active_scored_calls,


        -- ====================================================
        -- Active calls that cannot yet be scored
        -- ====================================================

        COUNT(*) FILTER (

            WHERE
                left_censored

                OR berth_detection_confidence <> 'high'

                OR berth_continuity = 'review'

                OR baseline_scope
                    = 'insufficient_history'

                OR expected_minutes IS NULL

        ) AS active_unscored_calls,


        -- ====================================================
        -- Active delayed calls
        -- ====================================================

        COUNT(*) FILTER (

            WHERE
                NOT left_censored

                AND berth_detection_confidence = 'high'

                AND berth_continuity <> 'review'

                AND baseline_scope
                    <> 'insufficient_history'

                AND p75_minutes IS NOT NULL

                AND elapsed_minutes_as_of_day
                    > p75_minutes

        ) AS active_delayed_calls,


        -- ====================================================
        -- Active severe calls
        -- ====================================================

        COUNT(*) FILTER (

            WHERE
                NOT left_censored

                AND berth_detection_confidence = 'high'

                AND berth_continuity <> 'review'

                AND baseline_scope
                    <> 'insufficient_history'

                AND p95_minutes IS NOT NULL

                AND elapsed_minutes_as_of_day
                    > p95_minutes

        ) AS active_severe_calls,


        -- ====================================================
        -- Mean excess duration among abnormal active calls
        -- ====================================================

        AVG(

            GREATEST(
                elapsed_minutes_as_of_day
                    - expected_minutes,
                0
            )

            / 60.0

        ) FILTER (

            WHERE
                NOT left_censored

                AND berth_detection_confidence = 'high'

                AND berth_continuity <> 'review'

                AND baseline_scope
                    <> 'insufficient_history'

                AND expected_minutes IS NOT NULL

                AND p75_minutes IS NOT NULL

                AND elapsed_minutes_as_of_day
                    > p75_minutes

        ) AS active_mean_delay_hours,


        MAX(
            elapsed_minutes_as_of_day
        ) / 60.0
            AS max_active_elapsed_hours


    FROM active_call_day

    GROUP BY metric_date
),


-- ============================================================
-- 6. Completed delays
--
-- These are safe to use only from the day on which the call
-- actually finished.
-- ============================================================

completed_summary AS (

    SELECT

        daily.metric_date,


        COUNT(calls.validated_call_id) FILTER (

            WHERE calls.delay_band
                IN (
                    'elevated',
                    'high',
                    'severe'
                )

        ) AS delayed_departures,


        COUNT(calls.validated_call_id) FILTER (

            WHERE calls.delay_band = 'severe'

        ) AS severe_departures


    FROM daily


    LEFT JOIN public.lng_call_delay_metrics
        AS calls

        ON calls.berth_departure_time::date
           = daily.metric_date

        AND calls.delay_band <> 'unscored'


    GROUP BY daily.metric_date
),


-- ============================================================
-- 7. Combine daily features
-- ============================================================

combined AS (

    SELECT

        daily.metric_date,

        daily.arrivals,
        daily.departures,

        daily.terminal_utilisation_pct,
        daily.mean_occupied_berths,
        daily.max_occupied_berths,


        COALESCE(
            active.active_calls,
            0
        ) AS active_calls,


        COALESCE(
            active.active_scored_calls,
            0
        ) AS active_scored_calls,


        COALESCE(
            active.active_unscored_calls,
            0
        ) AS active_unscored_calls,


        COALESCE(
            active.active_delayed_calls,
            0
        ) AS active_delayed_calls,


        COALESCE(
            active.active_severe_calls,
            0
        ) AS active_severe_calls,


        active.active_mean_delay_hours,

        active.max_active_elapsed_hours,


        completed.delayed_departures,
        completed.severe_departures


    FROM daily


    LEFT JOIN active_summary AS active

        ON active.metric_date
           = daily.metric_date


    LEFT JOIN completed_summary AS completed

        ON completed.metric_date
           = daily.metric_date
),


-- ============================================================
-- 8. Trailing 3-day information
--
-- Current day + previous two days only.
-- ============================================================

rolling AS (

    SELECT
        *,


        SUM(arrivals) OVER (

            ORDER BY metric_date

            ROWS BETWEEN
                2 PRECEDING
                AND CURRENT ROW

        ) AS arrivals_3d,


        SUM(departures) OVER (

            ORDER BY metric_date

            ROWS BETWEEN
                2 PRECEDING
                AND CURRENT ROW

        ) AS departures_3d,


        AVG(
            terminal_utilisation_pct
        ) OVER (

            ORDER BY metric_date

            ROWS BETWEEN
                2 PRECEDING
                AND CURRENT ROW

        ) AS utilisation_3d_avg,


        SUM(
            severe_departures
        ) OVER (

            ORDER BY metric_date

            ROWS BETWEEN
                2 PRECEDING
                AND CURRENT ROW

        ) AS severe_departures_3d


    FROM combined
)


-- ============================================================
-- 9. Final risk features
-- ============================================================

SELECT

    metric_date,

    arrivals,
    departures,

    terminal_utilisation_pct,

    mean_occupied_berths,
    max_occupied_berths,


    -- --------------------------------------------------------
    -- Capacity pressure: [0, 1]
    -- --------------------------------------------------------

    LEAST(

        GREATEST(
            terminal_utilisation_pct / 100.0,
            0
        ),

        1

    ) AS capacity_pressure,


    -- --------------------------------------------------------
    -- Peak berth saturation: [0, 1]
    -- --------------------------------------------------------

    LEAST(

        GREATEST(
            max_occupied_berths / 3.0,
            0
        ),

        1

    ) AS berth_saturation,


    active_calls,
    active_scored_calls,
    active_unscored_calls,

    active_delayed_calls,
    active_severe_calls,

    active_mean_delay_hours,

    max_active_elapsed_hours,


    -- --------------------------------------------------------
    -- Active delay share
    -- --------------------------------------------------------

    CASE

        WHEN active_scored_calls > 0

        THEN
            active_delayed_calls::numeric
            /
            active_scored_calls

        ELSE 0

    END AS active_delay_share,


    -- --------------------------------------------------------
    -- Severe active-delay share
    -- --------------------------------------------------------

    CASE

        WHEN active_scored_calls > 0

        THEN
            active_severe_calls::numeric
            /
            active_scored_calls

        ELSE 0

    END AS active_severe_share,


    -- --------------------------------------------------------
    -- Data-quality pressure
    -- --------------------------------------------------------

    CASE

        WHEN active_calls > 0

        THEN
            active_unscored_calls::numeric
            /
            active_calls

        ELSE 0

    END AS unscored_active_share,


    delayed_departures,
    severe_departures,


    arrivals_3d,
    departures_3d,

    utilisation_3d_avg,

    severe_departures_3d,


    arrivals_3d
        - departures_3d
        AS vessel_balance_3d,


    GREATEST(

        arrivals_3d
        - departures_3d,

        0

    ) AS positive_vessel_balance_3d


FROM rolling;


CREATE UNIQUE INDEX
idx_lng_terminal_risk_features_date

ON public.lng_terminal_risk_features_daily (
    metric_date
);


ANALYZE public.lng_terminal_risk_features_daily;