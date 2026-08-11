BEGIN;

CREATE TABLE IF NOT EXISTS public.terminal_zones (
    zone_id BIGSERIAL PRIMARY KEY,

    terminal_id INTEGER NOT NULL
        REFERENCES public.terminals(terminal_id),

    zone_code TEXT NOT NULL UNIQUE,
    zone_name TEXT NOT NULL,

    zone_type TEXT NOT NULL
        CHECK (
            zone_type IN (
                'berth',
                'anchorage',
                'manoeuvring_basin',
                'shipping_channel',
                'approach'
            )
        ),

    berth_number INTEGER,

    -- Lower number wins when zones overlap.
    zone_priority INTEGER NOT NULL,

    valid_from DATE,
    valid_to DATE,

    source_name TEXT NOT NULL,
    source_reference TEXT,
    geometry_confidence TEXT NOT NULL DEFAULT 'medium'
        CHECK (
            geometry_confidence IN (
                'high',
                'medium',
                'low'
            )
        ),

    notes TEXT,

    geom geometry(MultiPolygon, 4326) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        (
            zone_type = 'berth'
            AND berth_number IS NOT NULL
        )
        OR
        (
            zone_type <> 'berth'
            AND berth_number IS NULL
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_terminal_zones_terminal
ON public.terminal_zones (terminal_id);

CREATE INDEX IF NOT EXISTS idx_terminal_zones_type
ON public.terminal_zones (zone_type);

CREATE INDEX IF NOT EXISTS idx_terminal_zones_geom
ON public.terminal_zones
USING GIST (geom);

COMMIT;
