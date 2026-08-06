CREATE EXTENSION IF NOT EXISTS postgis;

DROP TABLE IF EXISTS staging_ais_positions;
DROP TABLE IF EXISTS ais_positions;
DROP TABLE IF EXISTS vessels;
DROP TABLE IF EXISTS terminals;

CREATE TABLE vessels (
    mmsi BIGINT PRIMARY KEY,
    imo BIGINT,
    vessel_name TEXT,
    call_sign TEXT,
    vessel_type INTEGER,
    length_metres DOUBLE PRECISION,
    width_metres DOUBLE PRECISION,
    cargo INTEGER,
    transceiver_class TEXT
);

CREATE TABLE terminals (
    terminal_id SERIAL PRIMARY KEY,
    terminal_name TEXT NOT NULL UNIQUE,
    country_code CHAR(2) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    detection_radius_metres INTEGER NOT NULL DEFAULT 5000,

    location GEOGRAPHY(POINT, 4326)
    GENERATED ALWAYS AS (
        ST_SetSRID(
            ST_MakePoint(longitude, latitude),
            4326
        )::geography
    ) STORED
);

CREATE TABLE ais_positions (
    mmsi BIGINT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    speed_knots DOUBLE PRECISION,
    course_degrees DOUBLE PRECISION,
    heading_degrees DOUBLE PRECISION,
    status INTEGER,
    draught_metres DOUBLE PRECISION,

    location GEOGRAPHY(POINT, 4326)
    GENERATED ALWAYS AS (
        ST_SetSRID(
            ST_MakePoint(longitude, latitude),
            4326
        )::geography
    ) STORED,

    PRIMARY KEY (mmsi, recorded_at),

    CONSTRAINT fk_ais_vessel
        FOREIGN KEY (mmsi)
        REFERENCES vessels (mmsi)
);

CREATE INDEX idx_ais_positions_location
ON ais_positions
USING GIST (location);

CREATE INDEX idx_ais_positions_recorded_at
ON ais_positions (recorded_at);

CREATE INDEX idx_ais_positions_mmsi
ON ais_positions (mmsi);

-- Temporary loading area used before data is split into final tables.
CREATE UNLOGGED TABLE staging_ais_positions (
    mmsi BIGINT,
    recorded_at TIMESTAMPTZ,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    speed_knots DOUBLE PRECISION,
    course_degrees DOUBLE PRECISION,
    heading_degrees DOUBLE PRECISION,
    vessel_name TEXT,
    imo BIGINT,
    call_sign TEXT,
    vessel_type INTEGER,
    status INTEGER,
    length_metres DOUBLE PRECISION,
    width_metres DOUBLE PRECISION,
    draught_metres DOUBLE PRECISION,
    cargo INTEGER,
    transceiver_class TEXT
);