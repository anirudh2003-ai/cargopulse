-- ============================================================
-- CargoPulse Phase 2E
--
-- Build the operational zone timeline for every confirmed
-- LNG call.
--
-- Each call receives a chronological sequence of:
--
--   APPROACH
--   CHANNEL
--   MANOEUVRE
--   BERTH
--   MANOEUVRE
--   CHANNEL
--   APPROACH
--
-- Short repeated observations of the same zone are grouped
-- into episodes.
-- ============================================================


DROP MATERIALIZED VIEW IF EXISTS
    public.lng_call_zone_timeline;


CREATE MATERIALIZED VIEW
public.lng_call_zone_timeline
AS


-- ------------------------------------------------------------
-- 1. Pull primary-zone AIS observations belonging to each
--    operational LNG call.
--
-- We use the original proximity call window because it
-- naturally contains the inbound/outbound movements around
-- the berth stay.
--
-- Add two hours of context either side.
-- ------------------------------------------------------------

WITH call_points AS (

    SELECT
        calls.validated_call_id,
        calls.mmsi,
        calls.imo,
        calls.vessel_name,

        calls.berth_zone_code,

        calls.berth_arrival_time,
        calls.berth_departure_time,

        zones.recorded_at,

        zones.terminal_id,
        zones.zone_code,
        zones.zone_type,
        zones.zone_priority,

        positions.speed_knots

    FROM public.lng_operational_calls AS calls

    JOIN public.ais_position_primary_zone AS zones

        ON zones.mmsi = calls.mmsi

        AND zones.recorded_at
            >= calls.original_arrival_time
               - INTERVAL '2 hours'

        AND zones.recorded_at
            <= calls.original_departure_time
               + INTERVAL '2 hours'

    JOIN public.ais_positions AS positions

        ON positions.mmsi
            = zones.mmsi

        AND positions.recorded_at
            = zones.recorded_at
),


-- ------------------------------------------------------------
-- 2. Determine previous zone and previous observation.
-- ------------------------------------------------------------

ordered AS (

    SELECT
        *,

        LAG(recorded_at) OVER (

            PARTITION BY validated_call_id

            ORDER BY recorded_at

        ) AS previous_time,


        LAG(zone_code) OVER (

            PARTITION BY validated_call_id

            ORDER BY recorded_at

        ) AS previous_zone

    FROM call_points
),


-- ------------------------------------------------------------
-- 3. Start a new episode when:
--
--      - zone changes
--      - AIS gap > 20 minutes
--
-- ------------------------------------------------------------

marked AS (

    SELECT
        *,

        CASE

            WHEN previous_time IS NULL
                THEN 1

            WHEN recorded_at - previous_time
                    > INTERVAL '20 minutes'
                THEN 1

            WHEN zone_code
                    IS DISTINCT FROM previous_zone
                THEN 1

            ELSE 0

        END AS starts_new_episode

    FROM ordered
),


-- ------------------------------------------------------------
-- 4. Give every episode an integer number.
-- ------------------------------------------------------------

numbered AS (

    SELECT
        *,

        SUM(starts_new_episode) OVER (

            PARTITION BY validated_call_id

            ORDER BY recorded_at

            ROWS BETWEEN
                UNBOUNDED PRECEDING
                AND CURRENT ROW

        ) AS episode_number

    FROM marked
),


-- ------------------------------------------------------------
-- 5. Collapse the AIS observations into episodes.
-- ------------------------------------------------------------

episodes AS (

    SELECT
        validated_call_id,

        MAX(mmsi)
            AS mmsi,

        MAX(imo)
            AS imo,

        MAX(vessel_name)
            AS vessel_name,

        MAX(berth_zone_code)
            AS berth_zone_code,

        terminal_id,
        zone_code,
        zone_type,
        zone_priority,

        episode_number,

        MIN(recorded_at)
            AS episode_start,

        MAX(recorded_at)
            AS episode_end,

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

        MAX(berth_arrival_time)
            AS berth_arrival_time,

        MAX(berth_departure_time)
            AS berth_departure_time

    FROM numbered

    GROUP BY
        validated_call_id,
        terminal_id,
        zone_code,
        zone_type,
        zone_priority,
        episode_number
)


-- ------------------------------------------------------------
-- 6. Add operational direction.
--
-- inbound:
--     before berth entry
--
-- berth:
--     overlaps reconstructed berth window
--
-- outbound:
--     after berth exit
-- ------------------------------------------------------------

SELECT
    *,

    CASE

        WHEN zone_type = 'berth'
             AND episode_end >= berth_arrival_time
             AND episode_start <= berth_departure_time
            THEN 'berth'

        WHEN episode_end < berth_arrival_time
            THEN 'inbound'

        WHEN episode_start > berth_departure_time
            THEN 'outbound'

        ELSE 'berth_transition'

    END AS movement_phase

FROM episodes;


CREATE UNIQUE INDEX
idx_lng_call_zone_timeline_unique

ON public.lng_call_zone_timeline (
    validated_call_id,
    episode_number
);


CREATE INDEX
idx_lng_call_zone_timeline_call

ON public.lng_call_zone_timeline (
    validated_call_id,
    episode_start
);


CREATE INDEX
idx_lng_call_zone_timeline_zone

ON public.lng_call_zone_timeline (
    zone_code,
    movement_phase
);


ANALYZE public.lng_call_zone_timeline;
