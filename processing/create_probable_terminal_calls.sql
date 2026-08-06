CREATE OR REPLACE VIEW probable_terminal_calls AS

WITH dataset_bounds AS (
    SELECT
        MIN(recorded_at) AS dataset_start,
        MAX(recorded_at) AS dataset_end
    FROM ais_positions
)

SELECT
    pc.port_call_id,
    pc.terminal_id,
    t.terminal_name,

    pc.mmsi,
    v.imo,
    v.vessel_name,
    v.vessel_type,
    v.length_metres,
    v.width_metres,

    pc.arrival_time,
    pc.departure_time,
    pc.duration_minutes,
    pc.position_count,

    pc.closest_distance_metres,
    pc.average_speed_knots,
    pc.maximum_speed_knots,

    pc.arrival_time
        <= bounds.dataset_start + INTERVAL '10 minutes'
        AS starts_at_dataset_boundary,

    pc.departure_time
        >= bounds.dataset_end - INTERVAL '10 minutes'
        AS ends_at_dataset_boundary

FROM port_calls pc

JOIN vessels v
    ON v.mmsi = pc.mmsi

JOIN terminals t
    ON t.terminal_id = pc.terminal_id

CROSS JOIN dataset_bounds bounds

WHERE
    t.terminal_name = 'Sabine Pass LNG'

    -- Remove short channel transits.
    AND pc.duration_minutes >= 360

    -- Vessel was mostly stationary.
    AND pc.average_speed_knots <= 1.0

    -- Vessel came reasonably close to the facility.
    AND pc.closest_distance_metres <= 2000

    -- Broad tanker vessel classification.
    AND v.vessel_type BETWEEN 80 AND 89

    -- LNG carriers are normally large vessels.
    AND (
        v.length_metres >= 250
        OR v.width_metres >= 40
    );
