{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 2E
-- Build a chronological operational-zone timeline around
-- each reconstructed LNG call.
-- ============================================================

with call_points as (

    select
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

    from {{ ref('int_lng_operational_calls') }} as calls

    join {{ ref('int_ais_position_primary_zone') }} as zones
        on zones.mmsi = calls.mmsi

        and zones.recorded_at
            >= calls.original_arrival_time
               - interval '2 hours'

        and zones.recorded_at
            <= calls.original_departure_time
               + interval '2 hours'

    join {{ ref('stg_ais_positions') }} as positions
        on positions.mmsi = zones.mmsi
        and positions.recorded_at = zones.recorded_at
),

ordered as (

    select
        *,

        lag(recorded_at) over (
            partition by validated_call_id
            order by recorded_at
        ) as previous_time,

        lag(zone_code) over (
            partition by validated_call_id
            order by recorded_at
        ) as previous_zone

    from call_points
),

marked as (

    select
        *,

        case

            when previous_time is null
                then 1

            when recorded_at - previous_time
                    > interval '20 minutes'
                then 1

            when zone_code is distinct from previous_zone
                then 1

            else 0

        end as starts_new_episode

    from ordered
),

numbered as (

    select
        *,

        sum(starts_new_episode) over (
            partition by validated_call_id
            order by recorded_at

            rows between
                unbounded preceding
                and current row
        ) as episode_number

    from marked
),

episodes as (

    select
        validated_call_id,

        max(mmsi)
            as mmsi,

        max(imo)
            as imo,

        max(vessel_name)
            as vessel_name,

        max(berth_zone_code)
            as berth_zone_code,

        terminal_id,
        zone_code,
        zone_type,
        zone_priority,

        episode_number,

        min(recorded_at)
            as episode_start,

        max(recorded_at)
            as episode_end,

        extract(
            epoch from (
                max(recorded_at)
                - min(recorded_at)
            )
        ) / 60.0
            as duration_minutes,

        count(*)
            as point_count,

        avg(speed_knots)
            as average_speed_knots,

        max(berth_arrival_time)
            as berth_arrival_time,

        max(berth_departure_time)
            as berth_departure_time

    from numbered

    group by
        validated_call_id,
        terminal_id,
        zone_code,
        zone_type,
        zone_priority,
        episode_number
)

select
    *,

    case

        when zone_type = 'berth'
             and episode_end >= berth_arrival_time
             and episode_start <= berth_departure_time
            then 'berth'

        when episode_end < berth_arrival_time
            then 'inbound'

        when episode_start > berth_departure_time
            then 'outbound'

        else 'berth_transition'

    end as movement_phase

from episodes
