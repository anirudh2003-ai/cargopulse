-- depends_on: {{ ref('stg_ais_positions') }}
{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 3C
-- Berth performance and utilisation
-- ============================================================

with bounds as (

    select
        min(recorded_at) as dataset_start,
        max(recorded_at) as dataset_end,

        extract(
            epoch from (
                max(recorded_at)
                - min(recorded_at)
            )
        ) / 60.0 as dataset_minutes

    from {{ ref('stg_ais_positions') }}
),

clipped_calls as (

    select

        calls.berth_zone_code,

        greatest(
            calls.berth_arrival_time,
            bounds.dataset_start
        ) as occupied_start,

        least(
            calls.berth_departure_time,
            bounds.dataset_end
        ) as occupied_end

    from {{ ref('int_lng_call_operations') }} as calls

    cross join bounds

    where
        calls.berth_arrival_time is not null
        and calls.berth_departure_time is not null
),

events_raw as (

    select
        berth_zone_code,
        occupied_start as event_time,
        1 as delta

    from clipped_calls

    where occupied_end > occupied_start

    union all

    select
        berth_zone_code,
        occupied_end as event_time,
        -1 as delta

    from clipped_calls

    where occupied_end > occupied_start
),

events as (

    select
        berth_zone_code,
        event_time,
        sum(delta) as delta

    from events_raw

    group by
        berth_zone_code,
        event_time
),

occupancy_running as (

    select

        berth_zone_code,
        event_time,

        sum(delta) over (
            partition by berth_zone_code
            order by event_time

            rows between
                unbounded preceding
                and current row
        ) as occupancy_count,

        lead(event_time) over (
            partition by berth_zone_code
            order by event_time
        ) as next_event_time

    from events
),

occupancy_summary as (

    select

        berth_zone_code,

        sum(
            case

                when occupancy_count > 0
                 and next_event_time is not null

                then extract(
                    epoch from (
                        next_event_time
                        - event_time
                    )
                ) / 60.0

                else 0

            end
        ) as occupied_minutes

    from occupancy_running

    group by berth_zone_code
),

call_summary as (

    select

        berth_zone_code,

        count(*) as total_calls,

        count(*) filter (
            where delay_band <> 'unscored'
        ) as scored_calls,

        count(*) filter (
            where delay_band = 'elevated'
        ) as elevated_calls,

        count(*) filter (
            where delay_band = 'high'
        ) as high_delay_calls,

        count(*) filter (
            where delay_band = 'severe'
        ) as severe_delay_calls,

        percentile_cont(0.50)
        within group (
            order by berth_duration_minutes
        ) as median_duration_minutes,

        percentile_cont(0.90)
        within group (
            order by berth_duration_minutes
        ) as p90_duration_minutes,

        avg(
            estimated_delay_minutes
        ) filter (
            where delay_band <> 'unscored'
        ) as mean_estimated_delay_minutes

    from {{ ref('lng_call_delay_metrics') }}

    group by berth_zone_code
)

select

    summary.berth_zone_code,

    summary.total_calls,
    summary.scored_calls,

    summary.elevated_calls,
    summary.high_delay_calls,
    summary.severe_delay_calls,

    summary.median_duration_minutes,
    summary.p90_duration_minutes,

    summary.mean_estimated_delay_minutes,

    occupancy.occupied_minutes,

    (
        occupancy.occupied_minutes
        / bounds.dataset_minutes
        * 100.0
    ) as utilisation_pct

from call_summary as summary

join occupancy_summary as occupancy
    on occupancy.berth_zone_code
       = summary.berth_zone_code

cross join bounds
