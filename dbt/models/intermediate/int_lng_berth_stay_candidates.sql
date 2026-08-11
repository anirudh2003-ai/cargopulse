{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 2C
-- Reconstruct LNG berth stays while tolerating short
-- geofence-boundary flicker.
-- ============================================================

with berth_points as (

    select
        calls.validated_call_id,
        calls.mmsi,
        calls.imo,
        calls.vessel_name,

        zones.terminal_id,
        zones.zone_code,

        zones.recorded_at,

        positions.speed_knots

    from {{ ref('stg_confirmed_lng_port_calls') }} as calls

    join {{ ref('int_ais_position_primary_zone') }} as zones
        on zones.mmsi = calls.mmsi

        and zones.recorded_at
            >= calls.arrival_time
               - interval '2 hours'

        and zones.recorded_at
            <= calls.departure_time
               + interval '2 hours'

    join {{ ref('stg_ais_positions') }} as positions
        on positions.mmsi = zones.mmsi
        and positions.recorded_at = zones.recorded_at

    where zones.zone_type = 'berth'
),

ordered as (

    select
        *,

        lag(recorded_at) over (
            partition by
                validated_call_id,
                zone_code

            order by recorded_at
        ) as previous_berth_time

    from berth_points
),

marked as (

    select
        *,

        case

            when previous_berth_time is null
                then 1

            when recorded_at - previous_berth_time
                    > interval '20 minutes'
                then 1

            else 0

        end as starts_new_stay

    from ordered
),

numbered as (

    select
        *,

        sum(starts_new_stay) over (
            partition by
                validated_call_id,
                zone_code

            order by recorded_at

            rows between
                unbounded preceding
                and current row
        ) as berth_stay_number

    from marked
)

select
    validated_call_id,

    mmsi,

    max(imo)
        as imo,

    max(vessel_name)
        as vessel_name,

    terminal_id,
    zone_code,

    berth_stay_number,

    min(recorded_at)
        as berth_start,

    max(recorded_at)
        as berth_end,

    max(recorded_at)
        - min(recorded_at)
        as berth_duration,

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

    avg(
        case
            when speed_knots is null
                then null

            when speed_knots < 0.5
                then 1.0

            else 0.0
        end
    ) as stationary_fraction

from numbered

group by
    validated_call_id,
    mmsi,
    terminal_id,
    zone_code,
    berth_stay_number
