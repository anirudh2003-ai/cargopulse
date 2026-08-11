{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 2F
-- Final operational record for each confirmed LNG call.
--
-- Converts the detailed geofence timeline into one concise
-- terminal-operation record per LNG vessel call.
-- ============================================================

with movement_summary as (

    select

        validated_call_id,

        -- Entire observed terminal-zone envelope
        min(episode_start)
            as first_zone_detection_time,

        max(episode_end)
            as last_zone_detection_time,


        -- Inbound
        min(episode_start) filter (
            where movement_phase = 'inbound'
        ) as inbound_start_time,

        min(episode_start) filter (
            where movement_phase = 'inbound'
              and zone_type = 'approach'
        ) as inbound_approach_time,

        min(episode_start) filter (
            where movement_phase = 'inbound'
              and zone_type = 'shipping_channel'
        ) as inbound_channel_time,

        min(episode_start) filter (
            where movement_phase = 'inbound'
              and zone_type = 'manoeuvring_basin'
        ) as inbound_manoeuvre_time,


        -- Outbound
        min(episode_start) filter (
            where movement_phase = 'outbound'
        ) as outbound_start_time,

        min(episode_start) filter (
            where movement_phase = 'outbound'
              and zone_type = 'manoeuvring_basin'
        ) as outbound_manoeuvre_time,

        min(episode_start) filter (
            where movement_phase = 'outbound'
              and zone_type = 'shipping_channel'
        ) as outbound_channel_time,

        max(episode_end) filter (
            where movement_phase = 'outbound'
              and zone_type = 'approach'
        ) as outbound_approach_exit_time,

        max(episode_end) filter (
            where movement_phase = 'outbound'
        ) as outbound_end_time,


        -- Coverage indicators
        count(*) filter (
            where movement_phase = 'inbound'
        ) as inbound_episode_count,

        count(*) filter (
            where movement_phase = 'outbound'
        ) as outbound_episode_count,

        count(*) filter (
            where movement_phase = 'inbound'
              and zone_type = 'approach'
        ) as inbound_approach_episodes,

        count(*) filter (
            where movement_phase = 'inbound'
              and zone_type = 'shipping_channel'
        ) as inbound_channel_episodes,

        count(*) filter (
            where movement_phase = 'inbound'
              and zone_type = 'manoeuvring_basin'
        ) as inbound_manoeuvre_episodes,

        count(*) filter (
            where movement_phase = 'outbound'
              and zone_type = 'manoeuvring_basin'
        ) as outbound_manoeuvre_episodes,

        count(*) filter (
            where movement_phase = 'outbound'
              and zone_type = 'shipping_channel'
        ) as outbound_channel_episodes,

        count(*) filter (
            where movement_phase = 'outbound'
              and zone_type = 'approach'
        ) as outbound_approach_episodes,

        count(*) filter (
            where duration_minutes < 2
        ) as very_short_episode_count,

        count(*)
            as total_timeline_episodes

    from {{ ref('int_lng_call_zone_timeline') }}

    group by validated_call_id
)

select

    calls.validated_call_id,

    calls.mmsi,
    calls.imo,
    calls.vessel_name,

    calls.terminal_id,
    calls.berth_zone_code,


    -- Geofence entry / exit
    movement.first_zone_detection_time,

    movement.inbound_start_time,

    movement.inbound_approach_time,

    movement.inbound_channel_time,

    movement.inbound_manoeuvre_time,


    -- Authoritative reconstructed berth timing
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


    -- Departure sequence
    movement.outbound_start_time,

    movement.outbound_manoeuvre_time,

    movement.outbound_channel_time,

    movement.outbound_approach_exit_time,

    movement.outbound_end_time,

    movement.last_zone_detection_time,


    -- Operational durations
    case

        when movement.inbound_start_time is not null
        then
            extract(
                epoch from (
                    calls.berth_arrival_time
                    - movement.inbound_start_time
                )
            ) / 60.0

        else null

    end as inbound_transit_minutes,


    case

        when movement.outbound_end_time is not null
        then
            extract(
                epoch from (
                    movement.outbound_end_time
                    - calls.berth_departure_time
                )
            ) / 60.0

        else null

    end as outbound_transit_minutes,


    case

        when movement.first_zone_detection_time is not null
         and movement.last_zone_detection_time is not null
        then
            extract(
                epoch from (
                    movement.last_zone_detection_time
                    - movement.first_zone_detection_time
                )
            ) / 60.0

        else null

    end as observed_terminal_cycle_minutes,


    -- Stage-presence flags
    (
        movement.inbound_approach_time is not null
    ) as has_inbound_approach,

    (
        movement.inbound_channel_time is not null
    ) as has_inbound_channel,

    (
        movement.inbound_manoeuvre_time is not null
    ) as has_inbound_manoeuvre,

    (
        movement.outbound_manoeuvre_time is not null
    ) as has_outbound_manoeuvre,

    (
        movement.outbound_channel_time is not null
    ) as has_outbound_channel,

    (
        movement.outbound_approach_exit_time is not null
    ) as has_outbound_approach,


    -- Timeline noise information
    movement.inbound_episode_count,

    movement.outbound_episode_count,

    movement.very_short_episode_count,

    movement.total_timeline_episodes,


    -- Overall movement coverage
    case

        when movement.inbound_start_time is not null
         and movement.outbound_end_time is not null
            then 'full'

        when movement.inbound_start_time is not null
         and movement.outbound_end_time is null
            then 'inbound_only'

        when movement.inbound_start_time is null
         and movement.outbound_end_time is not null
            then 'outbound_only'

        else 'berth_only'

    end as movement_coverage

from {{ ref('int_lng_operational_calls') }} as calls

left join movement_summary as movement
    on movement.validated_call_id
       = calls.validated_call_id
