BEGIN;

-- Add the fields required by the permanent PSIX registry.
ALTER TABLE public.vessel_registry
    ADD COLUMN IF NOT EXISTS imo BIGINT,
    ADD COLUMN IF NOT EXISTS mmsi BIGINT,

    ADD COLUMN IF NOT EXISTS ais_vessel_name TEXT,
    ADD COLUMN IF NOT EXISTS registry_vessel_name TEXT,

    ADD COLUMN IF NOT EXISTS psix_vessel_id BIGINT,

    ADD COLUMN IF NOT EXISTS service_type TEXT,
    ADD COLUMN IF NOT EXISTS service_sub_type TEXT,
    ADD COLUMN IF NOT EXISTS cargo_authorization TEXT,

    ADD COLUMN IF NOT EXISTS flag TEXT,
    ADD COLUMN IF NOT EXISTS vessel_status TEXT,

    ADD COLUMN IF NOT EXISTS classification_status TEXT,
    ADD COLUMN IF NOT EXISTS source_name TEXT,
    ADD COLUMN IF NOT EXISTS source_reference TEXT,

    ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ
        DEFAULT NOW(),

    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ
        DEFAULT NOW(),

    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
        DEFAULT NOW();

-- Required for ON CONFLICT (imo).
CREATE UNIQUE INDEX IF NOT EXISTS uq_vessel_registry_imo
ON public.vessel_registry (imo);

-- A PSIX internal vessel ID should identify only one registry row.
CREATE UNIQUE INDEX IF NOT EXISTS uq_vessel_registry_psix_vessel_id
ON public.vessel_registry (psix_vessel_id)
WHERE psix_vessel_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_vessel_registry_mmsi
ON public.vessel_registry (mmsi);

CREATE INDEX IF NOT EXISTS idx_vessel_registry_classification_status
ON public.vessel_registry (classification_status);

CREATE INDEX IF NOT EXISTS idx_vessel_registry_registry_name
ON public.vessel_registry (registry_vessel_name);

COMMIT;
