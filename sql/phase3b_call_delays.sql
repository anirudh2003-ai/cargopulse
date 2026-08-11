-- ============================================================
-- CargoPulse Phase 3B
-- Estimated operational delay per LNG call
-- ============================================================


DROP MATERIALIZED VIEW IF EXISTS
    public.lng_call_delay_metrics;


CREATE MATERIALIZED VIEW
public.lng_call_delay_metrics
AS


WITH dataset_bounds AS (

    SELECT
        MIN(recorded_at) AS dataset_start,
        MAX(recorded_at) AS dataset_end

    FROM public.ais_positions
),


baseline_input AS (

    SELECT

        calls.*,

        bounds.dataset_start,
        bounds.dataset_end,


        -- ----------------------------------------------------
        -- Prefer berth-specific baseline when enough samples
        -- exist. Otherwise use terminal-wide baseline.
        -- ----------------------------------------------------

        CASE
            WHEN berth_base.baseline_calls >= 5
                THEN 'berth'
            ELSE 'terminal'
        END AS baseline_scope,


        CASE
            WHEN berth_base.baseline_calls >= 5
                THEN berth_base.baseline_calls
            ELSE terminal_base.baseline_calls
        END AS baseline_sample_size,


        CASE
            WHEN berth_base.baseline_calls >= 5
                THEN berth_base.median_minutes
            ELSE terminal_base.median_minutes
        END AS expected_duration_minutes,


        CASE
            WHEN berth_base.baseline_calls >= 5
                THEN berth_base.p75_minutes
            ELSE terminal_base.p75_minutes
        END AS p75_minutes,


        CASE
            WHEN berth_base.baseline_calls >= 5
                THEN berth_base.p90_minutes
            ELSE terminal_base.p90_minutes
        END AS p90_minutes,


        CASE
            WHEN berth_base.baseline_calls >= 5
                THEN berth_base.p95_minutes
            ELSE terminal_base.p95_minutes
        END AS p95_minutes,


        CASE
            WHEN berth_base.baseline_calls >= 5
                THEN berth_base.iqr_minutes
            ELSE terminal_base.iqr_minutes
        END AS baseline_iqr_minutes


    FROM public.lng_call_operations AS calls


    LEFT JOIN public.lng_berth_duration_baseline
        AS berth_base

        ON berth_base.berth_zone_code
           = calls.berth_zone_code


    CROSS JOIN public.lng_terminal_duration_baseline
        AS terminal_base


    CROSS JOIN dataset_bounds AS bounds
),


quality AS (

    SELECT
        *,

        (
            berth_arrival_time
            <= dataset_start + INTERVAL '10 minutes'
        ) AS left_censored,

        (
            berth_departure_time
            >= dataset_end - INTERVAL '10 minutes'
        ) AS right_censored

    FROM baseline_input
),


scored AS (

    SELECT
        *,

        berth_duration_minutes
            - expected_duration_minutes
            AS duration_variance_minutes,


        GREATEST(
            berth_duration_minutes
            - expected_duration_minutes,
            0
        ) AS estimated_delay_minutes,


        CASE

            WHEN left_censored
              OR right_censored
                THEN 'censored'

            WHEN berth_continuity = 'review'
                THEN 'review'

            WHEN berth_continuity = 'moderate_gap'
                THEN 'usable_with_gap'

            WHEN berth_detection_confidence <> 'high'
                THEN 'lower_confidence'

            ELSE 'usable'

        END AS delay_quality

    FROM quality
)


SELECT
    *,

    estimated_delay_minutes / 60.0
        AS estimated_delay_hours,


    CASE

        WHEN delay_quality IN (
            'censored',
            'review',
            'lower_confidence'
        )
            THEN 'unscored'

        WHEN berth_duration_minutes <= p75_minutes
            THEN 'normal'

        WHEN berth_duration_minutes <= p90_minutes
            THEN 'elevated'

        WHEN berth_duration_minutes <= p95_minutes
            THEN 'high'

        ELSE 'severe'

    END AS delay_band

FROM scored;


CREATE UNIQUE INDEX
idx_lng_call_delay_metrics_id

ON public.lng_call_delay_metrics (
    validated_call_id
);


CREATE INDEX
idx_lng_call_delay_metrics_band

ON public.lng_call_delay_metrics (
    delay_band
);


ANALYZE public.lng_call_delay_metrics;
