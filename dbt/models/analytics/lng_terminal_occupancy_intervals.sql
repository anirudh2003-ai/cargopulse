{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 3D
-- Terminal occupancy intervals
-- ============================================================

with bounds as (

    select
        min(recorded_at) as dataset_start,
        max(recorded_at) as dataset_end

    from {{ ref('stg_ais_positions') }}
),

calls as (

    select

        validated_call_id,
        berth_zone_code,

        greatest(
            berth_arrival_time,
            dataset_start
        ) as occupied_start,

        least(
            berth_departure_time,
            dataset_end
        ) as occupied_end

    from {{ ref('int_lng_call_operations') }}

    cross join bounds

    where
        berth_arrival_time is not null
        and berth_departure_time is not null
),

event_times as (

    select occupied_start as event_time
    from calls

    union

    select occupied_end as event_time
    from calls
),

intervals as (

    select

        event_time as interval_start,

        lead(event_time) over (
            order by event_time
        ) as interval_end

    from event_times
)

select

    intervals.interval_start,
    intervals.interval_end,

    (
        select count(distinct calls.berth_zone_code)

        from calls

        where
            calls.occupied_start < intervals.interval_end
            and calls.occupied_end > intervals.interval_start

    ) as occupied_berths,

    (
        select count(*)

        from calls

        where
            calls.occupied_start < intervals.interval_end
            and calls.occupied_end > intervals.interval_start

    ) as active_calls,

    extract(
        epoch from (
            intervals.interval_end
            - intervals.interval_start
        )
    ) / 60.0 as duration_minutes

from intervals

where intervals.interval_end is not null
