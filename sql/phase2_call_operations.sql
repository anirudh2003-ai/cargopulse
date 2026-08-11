-- ============================================================
-- CargoPulse Phase 2F
--
-- Final operational record for each confirmed LNG call.
--
-- Converts the detailed geofence timeline into one concise
-- terminal-operation record per LNG vessel call.
-- ============================================================


DROP MATERIALIZED VIEW IF EXISTS
    public.lng_call_operations;


CREATE MATERIALIZED VIEW
public.lng_call_operations
AS


-- ------------------------------------------------------------
-- 1. Summarise NON-BERTH movement around each call.
--
-- Berth timing comes from lng_operational_calls because that
-- table already contains the reconstructed berth window.
-- ------------------------------------------------------------

WITH movement_summary AS (

    SELECT

        validated_call_id,


        -- ====================================================
        -- Entire observed terminal-zone envelope
        -- ====================================================

        MIN(episode_start)
            AS first_zone_detection_time,

        MAX(episode_end)
            AS last_zone_detection_time,


        -- ====================================================
        -- Inbound
        -- ====================================================

        MIN(episode_start) FILTER (
            WHERE movement_phase = 'inbound'
        ) AS inbound_start_time,


        MIN(episode_start) FILTER (
            WHERE movement_phase = 'inbound'
              AND zone_type = 'approach'
        ) AS inbound_approach_time,


        MIN(episode_start) FILTER (
            WHERE movement_phase = 'inbound'
              AND zone_type = 'shipping_channel'
        ) AS inbound_channel_time,


        MIN(episode_start) FILTER (
            WHERE movement_phase = 'inbound'
              AND zone_type = 'manoeuvring_basin'
        ) AS inbound_manoeuvre_time,


        -- ====================================================
        -- Outbound
        -- ====================================================

        MIN(episode_start) FILTER (
            WHERE movement_phase = 'outbound'
        ) AS outbound_start_time,


        MIN(episode_start) FILTER (
            WHERE movement_phase = 'outbound'
              AND zone_type = 'manoeuvring_basin'
        ) AS outbound_manoeuvre_time,


        MIN(episode_start) FILTER (
            WHERE movement_phase = 'outbound'
              AND zone_type = 'shipping_channel'
        ) AS outbound_channel_time,


        MAX(episode_end) FILTER (
            WHERE movement_phase = 'outbound'
              AND zone_type = 'approach'
        ) AS outbound_approach_exit_time,


        MAX(episode_end) FILTER (
            WHERE movement_phase = 'outbound'
        ) AS outbound_end_time,


        -- ====================================================
        -- Coverage indicators
        -- ====================================================

        COUNT(*) FILTER (
            WHERE movement_phase = 'inbound'
        ) AS inbound_episode_count,


        COUNT(*) FILTER (
            WHERE movement_phase = 'outbound'
        ) AS outbound_episode_count,


        COUNT(*) FILTER (
            WHERE movement_phase = 'inbound'
              AND zone_type = 'approach'
        ) AS inbound_approach_episodes,


        COUNT(*) FILTER (
            WHERE movement_phase = 'inbound'
              AND zone_type = 'shipping_channel'
        ) AS inbound_channel_episodes,


        COUNT(*) FILTER (
            WHERE movement_phase = 'inbound'
              AND zone_type = 'manoeuvring_basin'
        ) AS inbound_manoeuvre_episodes,


        COUNT(*) FILTER (
            WHERE movement_phase = 'outbound'
              AND zone_type = 'manoeuvring_basin'
        ) AS outbound_manoeuvre_episodes,


        COUNT(*) FILTER (
            WHERE movement_phase = 'outbound'
              AND zone_type = 'shipping_channel'
        ) AS outbound_channel_episodes,


        COUNT(*) FILTER (
            WHERE movement_phase = 'outbound'
              AND zone_type = 'approach'
        ) AS outbound_approach_episodes,


        COUNT(*) FILTER (
            WHERE duration_minutes < 2
        ) AS very_short_episode_count,


        COUNT(*)
            AS total_timeline_episodes


    FROM public.lng_call_zone_timeline

    GROUP BY validated_call_id
)


SELECT

    calls.validated_call_id,

    calls.mmsi,
    calls.imo,
    calls.vessel_name,

    calls.terminal_id,
    calls.berth_zone_code,


    -- ========================================================
    -- Geofence entry / exit
    -- ========================================================

    movement.first_zone_detection_time,

    movement.inbound_start_time,

    movement.inbound_approach_time,

    movement.inbound_channel_time,

    movement.inbound_manoeuvre_time,


    -- ========================================================
    -- Authoritative reconstructed berth timing
    -- ========================================================

    calls.berth_arrival_time,

    calls.berth_departure_time,

    calls.berth_duration_minutes,

    calls.observed_berth_minutes,

    calls.bridged_minutes,

    calls.berth_point_count,

    calls.fragment_count,

    calls.largest_internal_gap_minutes,

    calls.stationary_fraction,

    calls.berth_detection_confidence,

    calls.berth_continuity,


    -- ========================================================
    -- Departure sequence
    -- ========================================================

    movement.outbound_start_time,

    movement.outbound_manoeuvre_time,

    movement.outbound_channel_time,

    movement.outbound_approach_exit_time,

    movement.outbound_end_time,

    movement.last_zone_detection_time,


    -- ========================================================
    -- Operational durations
    -- ========================================================

    CASE

        WHEN movement.inbound_start_time IS NOT NULL
        THEN
            EXTRACT(
                EPOCH FROM (
                    calls.berth_arrival_time
                    - movement.inbound_start_time
                )
            ) / 60.0

        ELSE NULL

    END AS inbound_transit_minutes,


    CASE

        WHEN movement.outbound_end_time IS NOT NULL
        THEN
            EXTRACT(
                EPOCH FROM (
                    movement.outbound_end_time
                    - calls.berth_departure_time
                )
            ) / 60.0

        ELSE NULL

    END AS outbound_transit_minutes,


    CASE

        WHEN movement.first_zone_detection_time IS NOT NULL
         AND movement.last_zone_detection_time IS NOT NULL
        THEN
            EXTRACT(
                EPOCH FROM (
                    movement.last_zone_detection_time
                    - movement.first_zone_detection_time
                )
            ) / 60.0

        ELSE NULL

    END AS observed_terminal_cycle_minutes,


    -- ========================================================
    -- Stage-presence flags
    -- ========================================================

    (
        movement.inbound_approach_time
        IS NOT NULL
    ) AS has_inbound_approach,


    (
        movement.inbound_channel_time
        IS NOT NULL
    ) AS has_inbound_channel,


    (
        movement.inbound_manoeuvre_time
        IS NOT NULL
    ) AS has_inbound_manoeuvre,


    (
        movement.outbound_manoeuvre_time
        IS NOT NULL
    ) AS has_outbound_manoeuvre,


    (
        movement.outbound_channel_time
        IS NOT NULL
    ) AS has_outbound_channel,


    (
        movement.outbound_approach_exit_time
        IS NOT NULL
    ) AS has_outbound_approach,


    -- ========================================================
    -- Timeline noise information
    -- ========================================================

    movement.inbound_episode_count,

    movement.outbound_episode_count,

    movement.very_short_episode_count,

    movement.total_timeline_episodes,


    -- ========================================================
    -- Overall movement coverage
    -- ========================================================

    CASE

        WHEN movement.inbound_start_time IS NOT NULL
         AND movement.outbound_end_time IS NOT NULL
            THEN 'full'

        WHEN movement.inbound_start_time IS NOT NULL
         AND movement.outbound_end_time IS NULL
            THEN 'inbound_only'

        WHEN movement.inbound_start_time IS NULL
         AND movement.outbound_end_time IS NOT NULL
            THEN 'outbound_only'

        ELSE 'berth_only'

    END AS movement_coverage


FROM public.lng_operational_calls AS calls

LEFT JOIN movement_summary AS movement

    ON movement.validated_call_id
       = calls.validated_call_id;


-- ============================================================
-- INDEXES
-- ============================================================

CREATE UNIQUE INDEX
idx_lng_call_operations_id

ON public.lng_call_operations (
    validated_call_id
);


CREATE INDEX
idx_lng_call_operations_mmsi

ON public.lng_call_operations (
    mmsi
);


CREATE INDEX
idx_lng_call_operations_berth

ON public.lng_call_operations (
    berth_zone_code
);


CREATE INDEX
idx_lng_call_operations_arrival

ON public.lng_call_operations (
    berth_arrival_time
);


ANALYZE public.lng_call_operations;
