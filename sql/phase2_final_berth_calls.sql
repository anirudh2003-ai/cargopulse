-- ============================================================
-- CargoPulse Phase 2D
--
-- Reconstruct one operational berth window per confirmed
-- LNG call.
--
-- IMPORTANT:
-- A real berth stay may contain several detected fragments
-- because of:
--
--   - AIS reporting gaps
--   - geofence boundary jitter
--   - temporary classification outside the berth polygon
--
-- Therefore we do NOT simply select the longest fragment.
-- ============================================================


DROP MATERIALIZED VIEW IF EXISTS
    public.lng_operational_calls;


CREATE MATERIALIZED VIEW
public.lng_operational_calls
AS


-- ------------------------------------------------------------
-- 1. Calculate gaps between fragments belonging to the
--    same call and same berth.
-- ------------------------------------------------------------

WITH fragments AS (

    SELECT
        candidates.*,

        LAG(berth_end) OVER (
            PARTITION BY
                validated_call_id,
                zone_code

            ORDER BY berth_start
        ) AS previous_fragment_end

    FROM public.lng_berth_stay_candidates
        AS candidates
),


-- ------------------------------------------------------------
-- 2. Combine evidence for each berth within each call.
-- ------------------------------------------------------------

berth_summary AS (

    SELECT

        validated_call_id,
        mmsi,

        MAX(imo)
            AS imo,

        MAX(vessel_name)
            AS vessel_name,

        terminal_id,
        zone_code,


        -- First time vessel was detected at this berth.
        MIN(berth_start)
            AS berth_arrival_time,


        -- Last time vessel was detected at this berth.
        MAX(berth_end)
            AS berth_departure_time,


        -- Number of separate detected fragments.
        COUNT(*)
            AS fragment_count,


        -- Number of actual berth AIS observations.
        SUM(point_count)
            AS berth_point_count,


        -- Time represented directly by detected fragments.
        SUM(duration_minutes)
            AS observed_berth_minutes,


        -- Complete first-to-last operational window.
        EXTRACT(
            EPOCH FROM (
                MAX(berth_end)
                - MIN(berth_start)
            )
        ) / 60.0
            AS berth_elapsed_minutes,


        -- Weighted stationary fraction.
        SUM(
            stationary_fraction
            * point_count
        )
        /
        NULLIF(
            SUM(point_count),
            0
        )
            AS stationary_fraction,


        -- Largest break between detected fragments.
        COALESCE(
            MAX(
                CASE

                    WHEN previous_fragment_end
                        IS NULL
                        THEN 0

                    ELSE
                        EXTRACT(
                            EPOCH FROM (
                                berth_start
                                - previous_fragment_end
                            )
                        ) / 60.0

                END
            ),
            0
        )
            AS largest_internal_gap_minutes


    FROM fragments

    GROUP BY
        validated_call_id,
        mmsi,
        terminal_id,
        zone_code
),


-- ------------------------------------------------------------
-- 3. If a call touches multiple berth polygons, select the
--    berth containing the strongest total AIS evidence.
-- ------------------------------------------------------------

ranked_berths AS (

    SELECT
        *,

        ROW_NUMBER() OVER (

            PARTITION BY
                validated_call_id

            ORDER BY
                berth_point_count DESC,
                observed_berth_minutes DESC,
                zone_code ASC

        ) AS berth_rank

    FROM berth_summary
),


best_berth AS (

    SELECT *
    FROM ranked_berths

    WHERE berth_rank = 1
)


-- ------------------------------------------------------------
-- 4. Final operational LNG call.
-- ------------------------------------------------------------

SELECT

    calls.validated_call_id,

    calls.mmsi,
    calls.imo,
    calls.vessel_name,


    berth.terminal_id,

    berth.zone_code
        AS berth_zone_code,


    -- Original proximity detector.
    calls.arrival_time
        AS original_arrival_time,

    calls.departure_time
        AS original_departure_time,


    -- New berth-geofence timing.
    berth.berth_arrival_time,

    berth.berth_departure_time,


    berth.berth_departure_time
        - berth.berth_arrival_time
        AS berth_duration,


    berth.berth_elapsed_minutes
        AS berth_duration_minutes,


    -- Directly observed time inside berth fragments.
    berth.observed_berth_minutes,


    -- Difference between reconstructed elapsed window
    -- and directly detected fragments.
    GREATEST(
        berth.berth_elapsed_minutes
        - berth.observed_berth_minutes,
        0
    ) AS bridged_minutes,


    berth.berth_point_count,

    berth.fragment_count,

    berth.largest_internal_gap_minutes,

    berth.stationary_fraction,


    -- --------------------------------------------------------
    -- Difference from original proximity-derived timing.
    -- --------------------------------------------------------

    EXTRACT(
        EPOCH FROM (
            berth.berth_arrival_time
            - calls.arrival_time
        )
    ) / 60.0
        AS arrival_difference_minutes,


    EXTRACT(
        EPOCH FROM (
            berth.berth_departure_time
            - calls.departure_time
        )
    ) / 60.0
        AS departure_difference_minutes,


    -- --------------------------------------------------------
    -- Detection quality.
    -- --------------------------------------------------------

    CASE

        WHEN berth.stationary_fraction >= 0.95
             AND berth.berth_elapsed_minutes >= 360
             AND berth.berth_point_count >= 20
            THEN 'high'

        WHEN berth.stationary_fraction >= 0.80
             AND berth.berth_elapsed_minutes >= 60
            THEN 'medium'

        ELSE 'low'

    END AS berth_detection_confidence,


    -- --------------------------------------------------------
    -- Continuity quality.
    --
    -- Kept separate from detection confidence because a
    -- vessel can clearly be at a berth even when AIS contains
    -- a sizeable internal gap.
    -- --------------------------------------------------------

    CASE

        WHEN berth.fragment_count = 1
            THEN 'continuous'

        WHEN berth.largest_internal_gap_minutes <= 60
            THEN 'minor_gaps'

        WHEN berth.largest_internal_gap_minutes <= 360
            THEN 'moderate_gap'

        ELSE 'review'

    END AS berth_continuity


FROM public.confirmed_lng_port_calls
    AS calls

LEFT JOIN best_berth AS berth

    ON berth.validated_call_id
       = calls.validated_call_id;


-- ============================================================
-- INDEXES
-- ============================================================

CREATE UNIQUE INDEX
idx_lng_operational_calls_id

ON public.lng_operational_calls (
    validated_call_id
);


CREATE INDEX
idx_lng_operational_calls_mmsi

ON public.lng_operational_calls (
    mmsi
);


CREATE INDEX
idx_lng_operational_calls_berth

ON public.lng_operational_calls (
    berth_zone_code
);


CREATE INDEX
idx_lng_operational_calls_time

ON public.lng_operational_calls (
    berth_arrival_time,
    berth_departure_time
);


ANALYZE public.lng_operational_calls;