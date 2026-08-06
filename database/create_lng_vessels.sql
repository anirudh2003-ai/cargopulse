CREATE TABLE IF NOT EXISTS lng_vessels (
    lng_vessel_id BIGSERIAL PRIMARY KEY,

    imo BIGINT UNIQUE,
    mmsi BIGINT UNIQUE,

    vessel_name TEXT NOT NULL,
    vessel_class TEXT NOT NULL,

    source_name TEXT NOT NULL,
    source_reference TEXT,
    verified_at DATE NOT NULL,
    notes TEXT,

    CHECK (
        imo IS NOT NULL
        OR mmsi IS NOT NULL
    )
);
