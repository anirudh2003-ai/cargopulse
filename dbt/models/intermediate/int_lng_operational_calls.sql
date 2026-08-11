{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 2D
-- Reconstruct the authoritative operational LNG berth call.
--
-- Multiple berth fragments belonging to the same physical stay
-- are combined. The dominant berth is selected using the
-- strongest total AIS evidence.
-- ============================================================

with fragments as (

    select
        candidates.*,

        lag(berth_end) over (
            partition by
                validated_call_id,
                zone_code

            order by berth_start
        ) as previous_fragment_end

    from {{ ref('int_lng_berth_stay_candidates') }} as candidates
),

berth_summary as (

    select

        validated_call_id,
        mmsi,

        max(imo)
            as imo,

        max(vessel_name)
            as vessel_name,

        terminal_id,
        zone_code,

        min(berth_start)
            as berth_arrival_time,

        max(berth_end)
            as berth_departure_time,

        count(*)
            as fragment_count,

        sum(point_count)
            as berth_point_count,

        sum(duration_minutes)
            as observed_berth_minutes,

        extract(
            epoch from (
                max(berth_end)
                - min(berth_start)
            )
        ) / 60.0
            as berth_elapsed_minutes,

        sum(
            stationary_fraction
            * point_count
        )
        /
        nullif(
            sum(point_count),
            0
        )
            as stationary_fraction,

        coalesce(
            max(
                case
                    when previous_fragment_end is null
                        then 0

                    else
                        extract(
                            epoch from (
                                berth_start
                                - previous_fragment_end
                            )
                        ) / 60.0
                end
            ),
            0
        ) as largest_internal_gap_minutes

    from fragments

    group by
        validated_call_id,
        mmsi,
        terminal_id,
        zone_code
),

ranked_berths as (

    select
        *,

        row_number() over (
            partition by validated_call_id

            order by
                berth_point_count desc,
                observed_berth_minutes desc,
                zone_code asc
        ) as berth_rank

    from berth_summary
),

best_berth as (

    select *
    from ranked_berths

    where berth_rank = 1
)

select

    calls.validated_call_id,

    calls.mmsi,
    calls.imo,
    calls.vessel_name,

    berth.terminal_id,

    berth.zone_code
        as berth_zone_code,

    calls.arrival_time
        as original_arrival_time,

    calls.departure_time
        as original_departure_time,

    berth.berth_arrival_time,

    berth.berth_departure_time,

    berth.berth_departure_time
        - berth.berth_arrival_time
        as berth_duration,

    berth.berth_elapsed_minutes
        as berth_duration_minutes,

    berth.observed_berth_minutes,

    greatest(
        berth.berth_elapsed_minutes
        - berth.observed_berth_minutes,
        0
    ) as bridged_minutes,

    berth.berth_point_count,

    berth.fragment_count,

    berth.largest_internal_gap_minutes,

    berth.stationary_fraction,

    extract(
        epoch from (
            berth.berth_arrival_time
            - calls.arrival_time
        )
    ) / 60.0
        as arrival_difference_minutes,

    extract(
        epoch from (
            berth.berth_departure_time
            - calls.departure_time
        )
    ) / 60.0
        as departure_difference_minutes,

    case

        when berth.stationary_fraction >= 0.95
             and berth.berth_elapsed_minutes >= 360
             and berth.berth_point_count >= 20
            then 'high'

        when berth.stationary_fraction >= 0.80
             and berth.berth_elapsed_minutes >= 60
            then 'medium'

        else 'low'

    end as berth_detection_confidence,

    case

        when berth.fragment_count = 1
            then 'continuous'

        when berth.largest_internal_gap_minutes <= 60
            then 'minor_gaps'

        when berth.largest_internal_gap_minutes <= 360
            then 'moderate_gap'

        else 'review'

    end as berth_continuity

from {{ ref('stg_confirmed_lng_port_calls') }} as calls

left join best_berth as berth
    on berth.validated_call_id
       = calls.validated_call_id
