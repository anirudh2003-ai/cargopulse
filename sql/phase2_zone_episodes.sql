-- ============================================================
-- CargoPulse Phase 2B
--
-- AIS positions
--      ↓
-- primary operational zone
--      ↓
-- continuous zone episodes
--
-- Episode breaks occur when:
--   1. the primary zone changes, OR
--   2. the AIS gap exceeds 20 minutes
-- ============================================================


-- ------------------------------------------------------------
-- CLEAN UP OLD VERSION
-- ------------------------------------------------------------

DROP MATERIALIZED VIEW IF EXISTS
    public.ais_zone_episodes;

DROP MATERIALIZED VIEW IF EXISTS
    public.ais_position_zone_state;


-- ============================================================
-- 1. COMPLETE AIS ZONE STATE
-- ============================================================
--
-- IMPORTANT:
--
-- ais_position_primary_zone only contains AIS observations that
-- intersect a terminal zone.
--
-- Here we LEFT JOIN it onto the original AIS table so that
-- observations outside every geofence are retained with:
--
--     zone_code = NULL
--
-- This lets us detect vessels leaving and re-entering a zone.
-- ============================================================

CREATE MATERIALIZED VIEW
public.ais_position_zone_state
AS
SELECT
    p.mmsi,
    p.recorded_at,

    p.latitude,
    p.longitude,
    p.speed_knots,
    p.course_degrees,
    p.heading_degrees,

    z.terminal_id,
    z.zone_code,
    z.zone_type,
    z.zone_priority

FROM public.ais_positions AS p

LEFT JOIN public.ais_position_primary_zone AS z
    ON  z.mmsi = p.mmsi
    AND z.recorded_at = p.recorded_at;


CREATE UNIQUE INDEX
idx_zone_state_position
ON public.ais_position_zone_state (
    mmsi,
    recorded_at
);


CREATE INDEX
idx_zone_state_zone
ON public.ais_position_zone_state (
    zone_code,
    recorded_at
);


ANALYZE public.ais_position_zone_state;


-- ============================================================
-- 2. CONVERT AIS STATES INTO CONTINUOUS EPISODES
-- ============================================================

CREATE MATERIALIZED VIEW
public.ais_zone_episodes
AS

WITH ordered AS (

    SELECT
        *,

        LAG(recorded_at) OVER (
            PARTITION BY mmsi
            ORDER BY recorded_at
        ) AS previous_time,

        LAG(zone_code) OVER (
            PARTITION BY mmsi
            ORDER BY recorded_at
        ) AS previous_zone

    FROM public.ais_position_zone_state
),


-- ------------------------------------------------------------
-- Mark the beginning of every new state episode.
-- ------------------------------------------------------------

marked AS (

    SELECT
        *,

        CASE

            -- First observation for vessel.
            WHEN previous_time IS NULL
                THEN 1

            -- Large AIS reporting gap.
            WHEN recorded_at - previous_time
                    > INTERVAL '20 minutes'
                THEN 1

            -- Zone changed.
            --
            -- IS DISTINCT FROM is important because it handles
            -- NULL correctly:
            --
            -- CHANNEL → NULL
            -- NULL → CHANNEL
            --
            -- both count as changes.
            WHEN zone_code IS DISTINCT FROM previous_zone
                THEN 1

            ELSE 0

        END AS starts_new_episode

    FROM ordered
),


-- ------------------------------------------------------------
-- Assign an episode number using cumulative sum.
-- ------------------------------------------------------------

numbered AS (

    SELECT
        *,

        SUM(starts_new_episode) OVER (
            PARTITION BY mmsi
            ORDER BY recorded_at

            ROWS BETWEEN
                UNBOUNDED PRECEDING
                AND CURRENT ROW
        ) AS episode_number

    FROM marked
)


-- ------------------------------------------------------------
-- Collapse many AIS observations into one episode.
-- ------------------------------------------------------------

SELECT
    mmsi,

    episode_number,

    terminal_id,
    zone_code,
    zone_type,
    zone_priority,

    MIN(recorded_at)
        AS episode_start,

    MAX(recorded_at)
        AS episode_end,

    MAX(recorded_at)
        - MIN(recorded_at)
        AS episode_duration,

    EXTRACT(
        EPOCH FROM (
            MAX(recorded_at)
            - MIN(recorded_at)
        )
    ) / 60.0
        AS duration_minutes,

    COUNT(*)
        AS point_count,

    AVG(speed_knots)
        AS average_speed_knots,

    MIN(speed_knots)
        AS minimum_speed_knots,

    MAX(speed_knots)
        AS maximum_speed_knots

FROM numbered

-- We used NULL states to identify boundaries,
-- but they are not operational terminal episodes.
WHERE zone_code IS NOT NULL

GROUP BY
    mmsi,
    episode_number,
    terminal_id,
    zone_code,
    zone_type,
    zone_priority;


CREATE UNIQUE INDEX
idx_zone_episodes_unique
ON public.ais_zone_episodes (
    mmsi,
    episode_number
);


CREATE INDEX
idx_zone_episodes_zone
ON public.ais_zone_episodes (
    zone_code,
    episode_start
);


CREATE INDEX
idx_zone_episodes_time
ON public.ais_zone_episodes (
    episode_start,
    episode_end
);


ANALYZE public.ais_zone_episodes;
