-- depends_on: {{ ref('lng_terminal_risk_features_daily') }}

{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 4B
-- Transparent 0-100 daily supply-risk score
-- ============================================================



-- ============================================================
-- 1. NORMALISE INPUT FEATURES TO [0, 1]
-- ============================================================

WITH normalised AS (

    SELECT

        features.*,


        -- Already normalised by Phase 4A.
        LEAST(
            GREATEST(
                capacity_pressure,
                0
            ),
            1
        ) AS capacity_signal,


        LEAST(
            GREATEST(
                berth_saturation,
                0
            ),
            1
        ) AS saturation_signal,


        LEAST(
            GREATEST(
                active_delay_share,
                0
            ),
            1
        ) AS active_delay_signal,


        LEAST(
            GREATEST(
                active_severe_share,
                0
            ),
            1
        ) AS active_severe_signal,


        -- ----------------------------------------------------
        -- Active delay intensity.
        --
        -- 24 hours excess or more = maximum signal.
        --
        -- Example:
        --   6 hours  -> 0.25
        --   12 hours -> 0.50
        --   24 hours -> 1.00
        -- ----------------------------------------------------

        LEAST(
            GREATEST(
                COALESCE(
                    active_mean_delay_hours,
                    0
                ) / 24.0,
                0
            ),
            1
        ) AS active_delay_intensity_signal,


        -- ----------------------------------------------------
        -- Trailing utilisation.
        --
        -- utilisation_3d_avg is stored as percentage.
        -- ----------------------------------------------------

        LEAST(
            GREATEST(
                utilisation_3d_avg / 100.0,
                0
            ),
            1
        ) AS utilisation_3d_signal,


        -- ----------------------------------------------------
        -- Backlog signal.
        --
        -- +2 net vessels over three days is considered maximum
        -- pressure for this small 3-berth terminal model.
        -- ----------------------------------------------------

        LEAST(
            GREATEST(
                positive_vessel_balance_3d / 2.0,
                0
            ),
            1
        ) AS backlog_signal


    FROM {{ ref('lng_terminal_risk_features_daily') }}
        AS features
),


-- ============================================================
-- 2. CALCULATE COMPONENT POINTS
-- ============================================================

components AS (

    SELECT

        *,


        capacity_signal
            * 20.0
            AS capacity_points,


        saturation_signal
            * 10.0
            AS saturation_points,


        active_delay_signal
            * 20.0
            AS active_delay_points,


        active_severe_signal
            * 15.0
            AS active_severe_points,


        active_delay_intensity_signal
            * 10.0
            AS delay_intensity_points,


        utilisation_3d_signal
            * 15.0
            AS utilisation_3d_points,


        backlog_signal
            * 10.0
            AS backlog_points


    FROM normalised
),


-- ============================================================
-- 3. SUM TO FINAL SCORE
-- ============================================================

scored AS (

    SELECT

        *,

        LEAST(
            GREATEST(

                capacity_points
                + saturation_points
                + active_delay_points
                + active_severe_points
                + delay_intensity_points
                + utilisation_3d_points
                + backlog_points,

                0

            ),
            100
        ) AS risk_score


    FROM components
)


-- ============================================================
-- 4. FINAL OUTPUT
-- ============================================================

SELECT

    metric_date,


    -- --------------------------------------------------------
    -- Final score
    -- --------------------------------------------------------

    ROUND(
        risk_score::numeric,
        1
    ) AS risk_score,


    CASE

        WHEN risk_score < 25
            THEN 'low'

        WHEN risk_score < 50
            THEN 'moderate'

        WHEN risk_score < 70
            THEN 'elevated'

        WHEN risk_score < 85
            THEN 'high'

        ELSE 'critical'

    END AS risk_level,


    -- --------------------------------------------------------
    -- Individual component contributions
    -- --------------------------------------------------------

    ROUND(
        capacity_points::numeric,
        1
    ) AS capacity_points,

    ROUND(
        saturation_points::numeric,
        1
    ) AS saturation_points,

    ROUND(
        active_delay_points::numeric,
        1
    ) AS active_delay_points,

    ROUND(
        active_severe_points::numeric,
        1
    ) AS active_severe_points,

    ROUND(
        delay_intensity_points::numeric,
        1
    ) AS delay_intensity_points,

    ROUND(
        utilisation_3d_points::numeric,
        1
    ) AS utilisation_3d_points,

    ROUND(
        backlog_points::numeric,
        1
    ) AS backlog_points,


    -- --------------------------------------------------------
    -- Original underlying evidence
    -- --------------------------------------------------------

    terminal_utilisation_pct,
    max_occupied_berths,

    active_calls,
    active_scored_calls,
    active_unscored_calls,

    active_delayed_calls,
    active_severe_calls,

    active_mean_delay_hours,

    active_delay_share,
    active_severe_share,

    utilisation_3d_avg,

    arrivals_3d,
    departures_3d,
    vessel_balance_3d,

    delayed_departures,
    severe_departures,
    severe_departures_3d,


    -- --------------------------------------------------------
    -- Data confidence.
    --
    -- IMPORTANT:
    -- This does not modify the score.
    --
    -- We expose uncertainty separately rather than pretending
    -- missing data means lower operational risk.
    -- --------------------------------------------------------

    ROUND(
        (
            1.0
            - unscored_active_share
        )::numeric,
        3
    ) AS data_coverage_score,


    CASE

        WHEN unscored_active_share <= 0.20
            THEN 'high'

        WHEN unscored_active_share <= 0.50
            THEN 'medium'

        ELSE 'low'

    END AS score_confidence


FROM scored
