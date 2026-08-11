{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 3D
-- Daily terminal utilisation and congestion metrics
-- ============================================================

with bounds as (

    select
        min(recorded_at) as dataset_start,
        max(recorded_at) as dataset_end

    from {{ ref('stg_ais_positions') }}
),

days as (

    select
        generate_series(
            date_trunc(
                'day',
                dataset_start
            ),

            date_trunc(
                'day',
                dataset_end
            ),

            interval '1 day'
        ) as day_start

    from bounds
),

daily_occupancy as (

    select

        days.day_start,

        coalesce(
            sum(

                extract(
                    epoch from (
                        least(
                            occupancy.interval_end,
                            days.day_start
                                + interval '1 day'
                        )
                        -
                        greatest(
                            occupancy.interval_start,
                            days.day_start
                        )
                    )
                ) / 60.0

                * occupancy.occupied_berths

            ) filter (

                where
                    occupancy.interval_end > days.day_start

                    and occupancy.interval_start
                        < days.day_start
                          + interval '1 day'

            ),

            0

        ) as occupied_berth_minutes,

        coalesce(
            max(
                occupancy.occupied_berths
            ) filter (

                where
                    occupancy.interval_end > days.day_start

                    and occupancy.interval_start
                        < days.day_start
                          + interval '1 day'

            ),

            0

        ) as max_occupied_berths

    from days

    left join {{ ref('lng_terminal_occupancy_intervals') }} as occupancy
        on occupancy.interval_end > days.day_start

        and occupancy.interval_start
            < days.day_start
              + interval '1 day'

    group by days.day_start
),

daily_calls as (

    select

        days.day_start,

        count(calls.validated_call_id)
        filter (

            where
                calls.berth_arrival_time >= days.day_start

                and calls.berth_arrival_time
                    < days.day_start
                      + interval '1 day'

                and calls.movement_coverage in (
                    'full',
                    'inbound_only'
                )

        ) as arrivals,

        count(calls.validated_call_id)
        filter (

            where
                calls.berth_departure_time >= days.day_start

                and calls.berth_departure_time
                    < days.day_start
                      + interval '1 day'

                and calls.movement_coverage in (
                    'full',
                    'outbound_only'
                )

        ) as departures,

        avg(
            calls.estimated_delay_minutes
        ) filter (

            where
                calls.berth_arrival_time >= days.day_start

                and calls.berth_arrival_time
                    < days.day_start
                      + interval '1 day'

                and calls.movement_coverage in (
                    'full',
                    'inbound_only'
                )

                and calls.delay_band <> 'unscored'

        ) as mean_arrival_delay_minutes,

        count(calls.validated_call_id)
        filter (

            where
                calls.berth_arrival_time >= days.day_start

                and calls.berth_arrival_time
                    < days.day_start
                      + interval '1 day'

                and calls.movement_coverage in (
                    'full',
                    'inbound_only'
                )

                and calls.delay_band = 'severe'

        ) as severe_delay_arrivals

    from days

    left join {{ ref('lng_call_delay_metrics') }} as calls

        on (
            calls.berth_arrival_time >= days.day_start

            and calls.berth_arrival_time
                < days.day_start
                  + interval '1 day'
        )

        or (
            calls.berth_departure_time >= days.day_start

            and calls.berth_departure_time
                < days.day_start
                  + interval '1 day'
        )

    group by days.day_start
)

select

    occupancy.day_start::date
        as metric_date,

    calls.arrivals,
    calls.departures,

    occupancy.occupied_berth_minutes,

    occupancy.max_occupied_berths,

    occupancy.occupied_berth_minutes
        / (3.0 * 1440.0)
        * 100.0
        as terminal_utilisation_pct,

    occupancy.occupied_berth_minutes
        / 1440.0
        as mean_occupied_berths,

    calls.mean_arrival_delay_minutes,

    calls.severe_delay_arrivals

from daily_occupancy as occupancy

join daily_calls as calls
    on calls.day_start = occupancy.day_start
