CREATE OR REPLACE VIEW probable_call_gap_analysis AS

WITH ordered_calls AS (
    SELECT
        port_call_id,
        terminal_id,
        terminal_name,
        mmsi,
        imo,
        vessel_name,
        arrival_time,
        departure_time,

        LEAD(port_call_id) OVER (
            PARTITION BY terminal_id, mmsi
            ORDER BY arrival_time
        ) AS next_port_call_id,

        LEAD(arrival_time) OVER (
            PARTITION BY terminal_id, mmsi
            ORDER BY arrival_time
        ) AS next_arrival_time

    FROM probable_terminal_calls
),

call_pairs AS (
    SELECT
        *,
        EXTRACT(
            EPOCH FROM (
                next_arrival_time - departure_time
            )
        ) / 3600.0 AS gap_hours

    FROM ordered_calls

    WHERE next_port_call_id IS NOT NULL
)

SELECT
    cp.port_call_id,
    cp.next_port_call_id,
    cp.terminal_id,
    cp.terminal_name,
    cp.mmsi,
    cp.imo,
    cp.vessel_name,

    cp.departure_time AS first_call_end,
    cp.next_arrival_time AS second_call_start,
    cp.gap_hours,

    COUNT(p.recorded_at) AS positions_during_gap,

    COUNT(p.recorded_at) FILTER (
        WHERE NOT ST_DWithin(
            p.location,
            t.location,
            t.detection_radius_metres
        )
    ) AS positions_outside_radius,

    COUNT(p.recorded_at) FILTER (
        WHERE ST_DWithin(
            p.location,
            t.location,
            t.detection_radius_metres
        )
    ) AS positions_inside_radius

FROM call_pairs cp

JOIN terminals t
    ON t.terminal_id = cp.terminal_id

LEFT JOIN ais_positions p
    ON p.mmsi = cp.mmsi
    AND p.recorded_at > cp.departure_time
    AND p.recorded_at < cp.next_arrival_time

GROUP BY
    cp.port_call_id,
    cp.next_port_call_id,
    cp.terminal_id,
    cp.terminal_name,
    cp.mmsi,
    cp.imo,
    cp.vessel_name,
    cp.departure_time,
    cp.next_arrival_time,
    cp.gap_hours;
