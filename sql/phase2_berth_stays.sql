-- ============================================================
-- CargoPulse Phase 2C
--
-- Reconstruct continuous LNG berth stays while tolerating
-- short geofence boundary flicker.
-- ============================================================


DROP MATERIALIZED VIEW IF EXISTS
    public.lng_berth_stay_candidates;


CREATE MATERIALIZED VIEW
public.lng_berth_stay_candidates
AS

WITH berth_points AS (

    SELECT
        calls.validated_call_id,
        calls.mmsi,
        calls.imo,
        calls.vessel_name,

        zones.terminal_id,
        zones.zone_code,

        zones.recorded_at,

        positions.speed_knots

    FROM public.confirmed_lng_port_calls AS calls

    JOIN public.ais_position_primary_zone AS zones
        ON zones.mmsi = calls.mmsi

        AND zones.recorded_at
            >= calls.arrival_time
               - INTERVAL '2 hours'

        AND zones.recorded_at
            <= calls.departure_time
               + INTERVAL '2 hours'

    JOIN public.ais_positions AS positions
        ON positions.mmsi = zones.mmsi
        AND positions.recorded_at = zones.recorded_at

    WHERE zones.zone_type = 'berth'
),


-- ------------------------------------------------------------
-- Look only at successive observations of THE SAME BERTH.
--
-- This means a few MANOEUVRE/CHANNEL classifications between
-- two berth points do not automatically split the stay.
-- ------------------------------------------------------------

ordered AS (

    SELECT
        *,

        LAG(recorded_at) OVER (
            PARTITION BY
                validated_call_id,
                zone_code
            ORDER BY recorded_at
        ) AS previous_berth_time

    FROM berth_points
),


marked AS (

    SELECT
        *,

        CASE

            WHEN previous_berth_time IS NULL
                THEN 1

            WHEN recorded_at - previous_berth_time
                    > INTERVAL '20 minutes'
                THEN 1

            ELSE 0

        END AS starts_new_stay

    FROM ordered
),


numbered AS (

    SELECT
        *,

        SUM(starts_new_stay) OVER (
            PARTITION BY
                validated_call_id,
                zone_code

            ORDER BY recorded_at

            ROWS BETWEEN
                UNBOUNDED PRECEDING
                AND CURRENT ROW
        ) AS berth_stay_number

    FROM marked
)


SELECT
    validated_call_id,

    mmsi,

    MAX(imo) AS imo,

    MAX(vessel_name) AS vessel_name,

    terminal_id,
    zone_code,

    berth_stay_number,

    MIN(recorded_at)
        AS berth_start,

    MAX(recorded_at)
        AS berth_end,

    MAX(recorded_at)
        - MIN(recorded_at)
        AS berth_duration,

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

    AVG(
        CASE
            WHEN speed_knots IS NULL
                THEN NULL

            WHEN speed_knots < 0.5
                THEN 1.0

            ELSE 0.0
        END
    ) AS stationary_fraction

FROM numbered

GROUP BY
    validated_call_id,
    mmsi,
    terminal_id,
    zone_code,
    berth_stay_number;


CREATE UNIQUE INDEX
idx_lng_berth_stay_candidates
ON public.lng_berth_stay_candidates (
    validated_call_id,
    zone_code,
    berth_stay_number
);


CREATE INDEX
idx_lng_berth_stay_candidates_time
ON public.lng_berth_stay_candidates (
    berth_start,
    berth_end
);


ANALYZE public.lng_berth_stay_candidates;
