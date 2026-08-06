-- Rebuild all detected port calls from terminal-position hits.
TRUNCATE TABLE port_calls RESTART IDENTITY;

WITH ordered_hits AS (
    SELECT
        terminal_id,
        terminal_name,
        mmsi,
        recorded_at,
        distance_metres,
        speed_knots,

        LAG(recorded_at) OVER (
            PARTITION BY terminal_id, mmsi
            ORDER BY recorded_at
        ) AS previous_hit_at

    FROM terminal_position_hits
),

marked_hits AS (
    SELECT
        *,

        CASE
            WHEN previous_hit_at IS NULL THEN 1

            WHEN recorded_at - previous_hit_at
                > INTERVAL '2 hours'
            THEN 1

            ELSE 0
        END AS starts_new_call

    FROM ordered_hits
),

grouped_hits AS (
    SELECT
        *,

        SUM(starts_new_call) OVER (
            PARTITION BY terminal_id, mmsi
            ORDER BY recorded_at
            ROWS BETWEEN UNBOUNDED PRECEDING
                AND CURRENT ROW
        ) AS call_group

    FROM marked_hits
),

candidate_calls AS (
    SELECT
        terminal_id,
        mmsi,
        call_group,

        MIN(recorded_at) AS arrival_time,
        MAX(recorded_at) AS departure_time,

        EXTRACT(
            EPOCH FROM (
                MAX(recorded_at) - MIN(recorded_at)
            )
        ) / 60.0 AS duration_minutes,

        COUNT(*) AS position_count,

        MIN(distance_metres)
            AS closest_distance_metres,

        AVG(speed_knots)
            AS average_speed_knots,

        MAX(speed_knots)
            AS maximum_speed_knots

    FROM grouped_hits

    GROUP BY
        terminal_id,
        mmsi,
        call_group
)

INSERT INTO port_calls (
    terminal_id,
    mmsi,
    arrival_time,
    departure_time,
    duration_minutes,
    position_count,
    closest_distance_metres,
    average_speed_knots,
    maximum_speed_knots
)

SELECT
    terminal_id,
    mmsi,
    arrival_time,
    departure_time,
    duration_minutes,
    position_count,
    closest_distance_metres,
    average_speed_knots,
    maximum_speed_knots

FROM candidate_calls

WHERE
    duration_minutes >= 30
    AND position_count >= 3

ORDER BY arrival_time;
