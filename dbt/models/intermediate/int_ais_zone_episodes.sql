{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 2B
-- Convert AIS position states into continuous zone episodes.
--
-- Episode break:
--   1. first AIS observation for vessel
--   2. AIS reporting gap > 20 minutes
--   3. primary zone changes
--
-- NULL states participate in boundary detection, but are
-- excluded from the final operational-zone episode output.
-- ============================================================

with ordered as (

    select
        *,

        lag(recorded_at) over (
            partition by mmsi
            order by recorded_at
        ) as previous_time,

        lag(zone_code) over (
            partition by mmsi
            order by recorded_at
        ) as previous_zone

    from {{ ref('int_ais_position_zone_state') }}
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
            partition by mmsi
            order by recorded_at

            rows between
                unbounded preceding
                and current row
        ) as episode_number

    from marked
)

select
    mmsi,

    episode_number,

    terminal_id,
    zone_code,
    zone_type,
    zone_priority,

    min(recorded_at)
        as episode_start,

    max(recorded_at)
        as episode_end,

    max(recorded_at)
        - min(recorded_at)
        as episode_duration,

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

    min(speed_knots)
        as minimum_speed_knots,

    max(speed_knots)
        as maximum_speed_knots

from numbered

-- NULL states define boundaries but are not terminal episodes.
where zone_code is not null

group by
    mmsi,
    episode_number,
    terminal_id,
    zone_code,
    zone_type,
    zone_priority
