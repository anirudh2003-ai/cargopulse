DROP MATERIALIZED VIEW IF EXISTS
    public.geofence_reference_positions;

CREATE MATERIALIZED VIEW
    public.geofence_reference_positions
AS

SELECT
    ROW_NUMBER() OVER (
        ORDER BY
            positions.mmsi,
            positions.recorded_at
    )::BIGINT AS position_id,

    positions.mmsi,

    positions.recorded_at
        AS position_timestamp,

    positions.latitude,
    positions.longitude,

    positions.speed_knots
        AS speed_over_ground,

    positions.course_degrees,
    positions.heading_degrees,
    positions.status,
    positions.draught_metres,

    positions.location::geometry(Point, 4326)
        AS geom,

    calls.validated_call_id,
    calls.imo,
    calls.vessel_name,
    calls.terminal_id,
    calls.terminal_name,
    calls.arrival_time,
    calls.departure_time

FROM public.ais_positions AS positions

JOIN public.confirmed_lng_port_calls AS calls
    ON calls.mmsi = positions.mmsi

   AND positions.recorded_at
       BETWEEN
           calls.arrival_time - INTERVAL '2 hours'
           AND
           calls.departure_time + INTERVAL '2 hours';


CREATE UNIQUE INDEX
    idx_geofence_reference_position_id
ON public.geofence_reference_positions (
    position_id
);


CREATE INDEX
    idx_geofence_reference_mmsi
ON public.geofence_reference_positions (
    mmsi
);


CREATE INDEX
    idx_geofence_reference_timestamp
ON public.geofence_reference_positions (
    position_timestamp
);


CREATE INDEX
    idx_geofence_reference_geom
ON public.geofence_reference_positions
USING GIST (
    geom
);
