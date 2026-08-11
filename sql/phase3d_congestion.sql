-- ============================================================
-- CargoPulse Phase 3D
-- Terminal occupancy and daily congestion metrics
-- ============================================================


DROP MATERIALIZED VIEW IF EXISTS
    public.lng_terminal_daily_metrics;

DROP MATERIALIZED VIEW IF EXISTS
    public.lng_terminal_occupancy_intervals;


-- ============================================================
-- TERMINAL OCCUPANCY INTERVALS
-- ============================================================

CREATE MATERIALIZED VIEW
public.lng_terminal_occupancy_intervals
AS


WITH bounds AS (

    SELECT
        MIN(recorded_at) AS dataset_start,
        MAX(recorded_at) AS dataset_end

    FROM public.ais_positions
),


calls AS (

    SELECT

        validated_call_id,
        berth_zone_code,

        GREATEST(
            berth_arrival_time,
            dataset_start
        ) AS occupied_start,

        LEAST(
            berth_departure_time,
            dataset_end
        ) AS occupied_end

    FROM public.lng_call_operations

    CROSS JOIN bounds

    WHERE
        berth_arrival_time IS NOT NULL
        AND berth_departure_time IS NOT NULL
),


event_times AS (

    SELECT occupied_start AS event_time
    FROM calls

    UNION

    SELECT occupied_end AS event_time
    FROM calls
),


intervals AS (

    SELECT

        event_time AS interval_start,

        LEAD(event_time) OVER (
            ORDER BY event_time
        ) AS interval_end

    FROM event_times
)


SELECT

    intervals.interval_start,
    intervals.interval_end,

    (
        SELECT COUNT(DISTINCT calls.berth_zone_code)

        FROM calls

        WHERE
            calls.occupied_start
                < intervals.interval_end

            AND calls.occupied_end
                > intervals.interval_start

    ) AS occupied_berths,

    (
        SELECT COUNT(*)

        FROM calls

        WHERE
            calls.occupied_start
                < intervals.interval_end

            AND calls.occupied_end
                > intervals.interval_start

    ) AS active_calls,


    EXTRACT(
        EPOCH FROM (
            intervals.interval_end
            - intervals.interval_start
        )
    ) / 60.0 AS duration_minutes


FROM intervals

WHERE intervals.interval_end IS NOT NULL;


CREATE INDEX
idx_terminal_occupancy_time

ON public.lng_terminal_occupancy_intervals (
    interval_start,
    interval_end
);


-- ============================================================
-- DAILY TERMINAL METRICS
-- ============================================================

CREATE MATERIALIZED VIEW
public.lng_terminal_daily_metrics
AS


WITH bounds AS (

    SELECT
        MIN(recorded_at) AS dataset_start,
        MAX(recorded_at) AS dataset_end

    FROM public.ais_positions
),


days AS (

    SELECT
        generate_series(
            date_trunc(
                'day',
                dataset_start
            ),

            date_trunc(
                'day',
                dataset_end
            ),

            INTERVAL '1 day'
        ) AS day_start

    FROM bounds
),


daily_occupancy AS (

    SELECT

        days.day_start,

        COALESCE(
            SUM(

                EXTRACT(
                    EPOCH FROM (
                        LEAST(
                            occupancy.interval_end,
                            days.day_start
                                + INTERVAL '1 day'
                        )
                        -
                        GREATEST(
                            occupancy.interval_start,
                            days.day_start
                        )
                    )
                ) / 60.0

                * occupancy.occupied_berths

            ) FILTER (

                WHERE
                    occupancy.interval_end
                        > days.day_start

                    AND occupancy.interval_start
                        < days.day_start
                          + INTERVAL '1 day'

            ),

            0

        ) AS occupied_berth_minutes,


        COALESCE(
            MAX(
                occupancy.occupied_berths
            ) FILTER (

                WHERE
                    occupancy.interval_end
                        > days.day_start

                    AND occupancy.interval_start
                        < days.day_start
                          + INTERVAL '1 day'

            ),

            0

        ) AS max_occupied_berths


    FROM days

    LEFT JOIN
        public.lng_terminal_occupancy_intervals
        AS occupancy

        ON occupancy.interval_end
            > days.day_start

        AND occupancy.interval_start
            < days.day_start
              + INTERVAL '1 day'

    GROUP BY days.day_start
),


daily_calls AS (

    SELECT

        days.day_start,


        -- ----------------------------------------------------
        -- OBSERVED ARRIVALS
        --
        -- Count an arrival only when we actually observed
        -- inbound movement before the berth stay.
        -- ----------------------------------------------------

        COUNT(calls.validated_call_id)
        FILTER (

            WHERE
                calls.berth_arrival_time
                    >= days.day_start

                AND calls.berth_arrival_time
                    < days.day_start
                      + INTERVAL '1 day'

                AND calls.movement_coverage
                    IN (
                        'full',
                        'inbound_only'
                    )

        ) AS arrivals,


        -- ----------------------------------------------------
        -- OBSERVED DEPARTURES
        --
        -- Count a departure only when outbound movement was
        -- actually observed after the berth stay.
        -- ----------------------------------------------------

        COUNT(calls.validated_call_id)
        FILTER (

            WHERE
                calls.berth_departure_time
                    >= days.day_start

                AND calls.berth_departure_time
                    < days.day_start
                      + INTERVAL '1 day'

                AND calls.movement_coverage
                    IN (
                        'full',
                        'outbound_only'
                    )

        ) AS departures,


        -- ----------------------------------------------------
        -- Mean estimated delay for scored arrivals.
        -- ----------------------------------------------------

        AVG(
            calls.estimated_delay_minutes
        ) FILTER (

            WHERE
                calls.berth_arrival_time
                    >= days.day_start

                AND calls.berth_arrival_time
                    < days.day_start
                      + INTERVAL '1 day'

                AND calls.movement_coverage
                    IN (
                        'full',
                        'inbound_only'
                    )

                AND calls.delay_band <> 'unscored'

        ) AS mean_arrival_delay_minutes,


        -- ----------------------------------------------------
        -- Severe-delay arrivals.
        -- ----------------------------------------------------

        COUNT(calls.validated_call_id)
        FILTER (

            WHERE
                calls.berth_arrival_time
                    >= days.day_start

                AND calls.berth_arrival_time
                    < days.day_start
                      + INTERVAL '1 day'

                AND calls.movement_coverage
                    IN (
                        'full',
                        'inbound_only'
                    )

                AND calls.delay_band = 'severe'

        ) AS severe_delay_arrivals


    FROM days


    LEFT JOIN public.lng_call_delay_metrics
        AS calls

        ON (
            calls.berth_arrival_time
                >= days.day_start

            AND calls.berth_arrival_time
                < days.day_start
                  + INTERVAL '1 day'
        )

        OR (
            calls.berth_departure_time
                >= days.day_start

            AND calls.berth_departure_time
                < days.day_start
                  + INTERVAL '1 day'
        )


    GROUP BY days.day_start
)


SELECT

    occupancy.day_start::date
        AS metric_date,

    calls.arrivals,
    calls.departures,

    occupancy.occupied_berth_minutes,

    occupancy.max_occupied_berths,


    occupancy.occupied_berth_minutes
        / (3.0 * 1440.0)
        * 100.0
        AS terminal_utilisation_pct,


    occupancy.occupied_berth_minutes
        / 1440.0
        AS mean_occupied_berths,


    calls.mean_arrival_delay_minutes,

    calls.severe_delay_arrivals


FROM daily_occupancy AS occupancy

JOIN daily_calls AS calls
    ON calls.day_start
       = occupancy.day_start;


CREATE UNIQUE INDEX
idx_lng_terminal_daily_metrics

ON public.lng_terminal_daily_metrics (
    metric_date
);
