-- depends_on: {{ ref('lng_terminal_risk_score_daily') }}

{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 4C
-- Human-readable daily risk explanations
-- ============================================================



-- ============================================================
-- 1. Start from the Phase 4B risk scores
-- ============================================================

WITH base AS (

    SELECT
        *,

        LAG(risk_score) OVER (
            ORDER BY metric_date
        ) AS previous_risk_score,

        LAG(risk_level) OVER (
            ORDER BY metric_date
        ) AS previous_risk_level

    FROM {{ ref('lng_terminal_risk_score_daily') }}
),


-- ============================================================
-- 2. Convert every component into an explanation candidate
-- ============================================================

driver_rows AS (

    -- --------------------------------------------------------
    -- Capacity
    -- --------------------------------------------------------

    SELECT

        metric_date,

        'capacity' AS driver_key,

        capacity_points AS driver_points,

        'Terminal utilisation '
        || ROUND(
            terminal_utilisation_pct::numeric,
            1
        )::text
        || '%'
        AS driver_text

    FROM base

    WHERE capacity_points > 0


    UNION ALL


    -- --------------------------------------------------------
    -- Peak berth saturation
    -- --------------------------------------------------------

    SELECT

        metric_date,

        'berth_saturation',

        saturation_points,

        CASE

            WHEN max_occupied_berths = 3
                THEN 'All 3 berths occupied at peak'

            ELSE
                max_occupied_berths::text
                || ' of 3 berths occupied at peak'

        END

    FROM base

    WHERE saturation_points > 0


    UNION ALL


    -- --------------------------------------------------------
    -- Active delayed calls
    -- --------------------------------------------------------

    SELECT

        metric_date,

        'active_delay',

        active_delay_points,

        active_delayed_calls::text
        || ' active call(s) above normal-duration threshold'

    FROM base

    WHERE active_delay_points > 0


    UNION ALL


    -- --------------------------------------------------------
    -- Severe active calls
    -- --------------------------------------------------------

    SELECT

        metric_date,

        'active_severe',

        active_severe_points,

        active_severe_calls::text
        || ' active severe-duration call(s)'

    FROM base

    WHERE active_severe_points > 0


    UNION ALL


    -- --------------------------------------------------------
    -- Excess duration intensity
    -- --------------------------------------------------------

    SELECT

        metric_date,

        'delay_intensity',

        delay_intensity_points,

        'Mean active excess duration '
        || ROUND(
            COALESCE(
                active_mean_delay_hours,
                0
            )::numeric,
            1
        )::text
        || ' h'

    FROM base

    WHERE delay_intensity_points > 0


    UNION ALL


    -- --------------------------------------------------------
    -- 3-day utilisation
    -- --------------------------------------------------------

    SELECT

        metric_date,

        'utilisation_3d',

        utilisation_3d_points,

        'Trailing 3-day utilisation '
        || ROUND(
            utilisation_3d_avg::numeric,
            1
        )::text
        || '%'

    FROM base

    WHERE utilisation_3d_points > 0


    UNION ALL


    -- --------------------------------------------------------
    -- Vessel backlog
    -- --------------------------------------------------------

    SELECT

        metric_date,

        'backlog',

        backlog_points,

        '3-day net vessel balance +'
        || vessel_balance_3d::text

    FROM base

    WHERE backlog_points > 0
),


-- ============================================================
-- 3. Rank risk drivers by contribution
-- ============================================================

ranked_drivers AS (

    SELECT

        *,

        ROW_NUMBER() OVER (

            PARTITION BY metric_date

            ORDER BY
                driver_points DESC,
                driver_key ASC

        ) AS driver_rank

    FROM driver_rows
),


-- ============================================================
-- 4. Pivot the top three drivers
-- ============================================================

driver_summary AS (

    SELECT

        metric_date,


        MAX(driver_text) FILTER (
            WHERE driver_rank = 1
        ) AS primary_driver,


        MAX(driver_points) FILTER (
            WHERE driver_rank = 1
        ) AS primary_driver_points,


        MAX(driver_text) FILTER (
            WHERE driver_rank = 2
        ) AS secondary_driver,


        MAX(driver_points) FILTER (
            WHERE driver_rank = 2
        ) AS secondary_driver_points,


        MAX(driver_text) FILTER (
            WHERE driver_rank = 3
        ) AS tertiary_driver,


        MAX(driver_points) FILTER (
            WHERE driver_rank = 3
        ) AS tertiary_driver_points


    FROM ranked_drivers

    GROUP BY metric_date
)


-- ============================================================
-- 5. Final explanation record
-- ============================================================

SELECT

    base.metric_date,

    base.risk_score,
    base.risk_level,

    base.score_confidence,


    -- --------------------------------------------------------
    -- One-day change
    -- --------------------------------------------------------

    ROUND(
        (
            base.risk_score
            - base.previous_risk_score
        )::numeric,
        1
    ) AS risk_change_1d,


    base.previous_risk_level,


    CASE

        WHEN base.previous_risk_score IS NULL
            THEN 'initial'

        WHEN base.risk_score
             - base.previous_risk_score >= 10
            THEN 'rising_fast'

        WHEN base.risk_score
             - base.previous_risk_score >= 3
            THEN 'rising'

        WHEN base.risk_score
             - base.previous_risk_score <= -10
            THEN 'falling_fast'

        WHEN base.risk_score
             - base.previous_risk_score <= -3
            THEN 'falling'

        ELSE 'stable'

    END AS risk_trend,


    -- --------------------------------------------------------
    -- Top drivers
    -- --------------------------------------------------------

    drivers.primary_driver,

    ROUND(
        drivers.primary_driver_points::numeric,
        1
    ) AS primary_driver_points,


    drivers.secondary_driver,

    ROUND(
        drivers.secondary_driver_points::numeric,
        1
    ) AS secondary_driver_points,


    drivers.tertiary_driver,

    ROUND(
        drivers.tertiary_driver_points::numeric,
        1
    ) AS tertiary_driver_points,


    -- --------------------------------------------------------
    -- Short dashboard headline
    -- --------------------------------------------------------

    UPPER(base.risk_level)
    || ' — '
    || base.risk_score::text
    || ' / 100'
    AS risk_headline,


    -- --------------------------------------------------------
    -- One-line explanation
    -- --------------------------------------------------------

    'Primary drivers: '
    || COALESCE(
        drivers.primary_driver,
        'none'
    )

    || CASE
        WHEN drivers.secondary_driver IS NOT NULL
        THEN
            '; '
            || drivers.secondary_driver
        ELSE ''
    END

    || CASE
        WHEN drivers.tertiary_driver IS NOT NULL
        THEN
            '; '
            || drivers.tertiary_driver
        ELSE ''
    END

    AS risk_explanation,


    -- --------------------------------------------------------
    -- Underlying operational evidence
    -- --------------------------------------------------------

    base.terminal_utilisation_pct,

    base.max_occupied_berths,

    base.active_calls,

    base.active_delayed_calls,

    base.active_severe_calls,

    base.active_mean_delay_hours,

    base.utilisation_3d_avg,

    base.arrivals_3d,
    base.departures_3d,
    base.vessel_balance_3d,


    -- --------------------------------------------------------
    -- Component scores retained for auditability
    -- --------------------------------------------------------

    base.capacity_points,

    base.saturation_points,

    base.active_delay_points,

    base.active_severe_points,

    base.delay_intensity_points,

    base.utilisation_3d_points,

    base.backlog_points


FROM base


LEFT JOIN driver_summary AS drivers

    ON drivers.metric_date
       = base.metric_date
