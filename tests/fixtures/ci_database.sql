BEGIN;

INSERT INTO public.terminals (
    terminal_name,
    country_code,
    latitude,
    longitude,
    detection_radius_metres
)
VALUES (
    'CargoPulse CI LNG Terminal',
    'US',
    29.7300,
    -93.8700,
    5000
);

INSERT INTO public.vessels (
    mmsi,
    imo,
    vessel_name,
    call_sign,
    vessel_type,
    length_metres,
    width_metres,
    cargo,
    transceiver_class
)
VALUES (
    123456789,
    9876543,
    'CARGOPULSE CI VESSEL',
    'CPCI',
    80,
    290.0,
    46.0,
    80,
    'A'
);

INSERT INTO public.ais_positions (
    mmsi,
    recorded_at,
    latitude,
    longitude,
    speed_knots,
    course_degrees,
    heading_degrees,
    status,
    draught_metres
)
VALUES
(
    123456789,
    '2023-01-01 00:00:00+00',
    29.7300,
    -93.8700,
    0.2,
    180.0,
    180.0,
    5,
    11.5
),
(
    123456789,
    '2023-01-01 00:10:00+00',
    29.7301,
    -93.8701,
    0.1,
    180.0,
    180.0,
    5,
    11.5
);

INSERT INTO public.terminal_zones (
    terminal_id,
    zone_code,
    zone_name,
    zone_type,
    berth_number,
    zone_priority,
    valid_from,
    valid_to,
    source_name,
    source_reference,
    geometry_confidence,
    notes,
    geom
)
SELECT
    terminal_id,
    'CI_BERTH_1',
    'CargoPulse CI Berth 1',
    'berth',
    1,
    1,
    DATE '2023-01-01',
    NULL,
    'cargopulse_ci',
    'deterministic_fixture',
    'high',
    'Small deterministic geometry used only by CI.',
    ST_Multi(
        ST_GeomFromText(
            'POLYGON((
                -93.8800 29.7200,
                -93.8600 29.7200,
                -93.8600 29.7400,
                -93.8800 29.7400,
                -93.8800 29.7200
            ))',
            4326
        )
    )
FROM public.terminals
WHERE terminal_name = 'CargoPulse CI LNG Terminal';

CREATE TABLE public.confirmed_lng_port_calls (
    validated_call_id BIGINT PRIMARY KEY,
    mmsi BIGINT NOT NULL,
    imo BIGINT,
    vessel_name TEXT NOT NULL,
    arrival_time TIMESTAMPTZ NOT NULL,
    departure_time TIMESTAMPTZ NOT NULL,

    CHECK (
        departure_time > arrival_time
    )
);

INSERT INTO public.confirmed_lng_port_calls (
    validated_call_id,
    mmsi,
    imo,
    vessel_name,
    arrival_time,
    departure_time
)
VALUES (
    1,
    123456789,
    9876543,
    'CARGOPULSE CI VESSEL',
    '2023-01-01 00:00:00+00',
    '2023-01-01 02:00:00+00'
);

COMMIT;
