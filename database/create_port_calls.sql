CREATE TABLE IF NOT EXISTS port_calls (
    port_call_id BIGSERIAL PRIMARY KEY,

    terminal_id INTEGER NOT NULL
        REFERENCES terminals (terminal_id),

    mmsi BIGINT NOT NULL
        REFERENCES vessels (mmsi),

    arrival_time TIMESTAMPTZ NOT NULL,
    departure_time TIMESTAMPTZ NOT NULL,

    duration_minutes DOUBLE PRECISION NOT NULL,
    position_count INTEGER NOT NULL,

    closest_distance_metres DOUBLE PRECISION,
    average_speed_knots DOUBLE PRECISION,
    maximum_speed_knots DOUBLE PRECISION,

    detection_method TEXT NOT NULL
        DEFAULT 'radius_and_time_gap',

    UNIQUE (
        terminal_id,
        mmsi,
        arrival_time
    )
);

CREATE INDEX IF NOT EXISTS idx_port_calls_terminal
ON port_calls (terminal_id);

CREATE INDEX IF NOT EXISTS idx_port_calls_mmsi
ON port_calls (mmsi);

CREATE INDEX IF NOT EXISTS idx_port_calls_arrival
ON port_calls (arrival_time);
