CREATE OR REPLACE VIEW terminal_position_hits AS
SELECT
    t.terminal_id,
    t.terminal_name,
    t.detection_radius_metres,
    p.mmsi,
    p.recorded_at,
    p.latitude,
    p.longitude,
    p.speed_knots,
    p.course_degrees,
    p.heading_degrees,
    p.status,
    p.draught_metres,
    ST_Distance(
        p.location,
        t.location
    ) AS distance_metres
FROM terminals t
JOIN ais_positions p
    ON ST_DWithin(
        p.location,
        t.location,
        t.detection_radius_metres
    );
