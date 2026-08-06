BEGIN;

CREATE TABLE IF NOT EXISTS vessel_registry (
    -- Permanent maritime identity.
    imo BIGINT PRIMARY KEY,

    -- Current or most recently observed AIS identity.
    -- MMSI can change, so it is not the primary key.
    mmsi BIGINT,

    -- Name observed in the NOAA AIS dataset.
    ais_vessel_name TEXT,

    -- Current name returned by USCG PSIX.
    registry_vessel_name TEXT,

    -- Internal identifier used by USCG PSIX.
    psix_vessel_id BIGINT UNIQUE,

    -- Broad and detailed classifications returned by PSIX.
    service_type TEXT,
    service_sub_type TEXT,
    cargo_authorization TEXT,

    flag TEXT,
    vessel_status TEXT,

    classification_status TEXT NOT NULL
        CHECK (
            classification_status IN (
                'confirmed_lng',
                'confirmed_non_lng',
                'needs_review',
                'unknown'
            )
        ),

    source_name TEXT NOT NULL,
    source_reference TEXT,

    -- When this classification was most recently checked.
    last_checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vessel_registry_mmsi
ON vessel_registry (mmsi);

CREATE INDEX IF NOT EXISTS idx_vessel_registry_classification_status
ON vessel_registry (classification_status);

CREATE INDEX IF NOT EXISTS idx_vessel_registry_registry_name
ON vessel_registry (registry_vessel_name);

COMMIT;
