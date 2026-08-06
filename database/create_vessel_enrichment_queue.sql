BEGIN;

CREATE TABLE IF NOT EXISTS public.vessel_enrichment_queue (
    lookup_key TEXT PRIMARY KEY,

    imo BIGINT,
    mmsi BIGINT,
    observed_vessel_name TEXT,

    queue_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            queue_status IN (
                'pending',
                'processing',
                'completed',
                'needs_review',
                'failed'
            )
        ),

    attempt_count INTEGER NOT NULL DEFAULT 0,

    last_attempt_at TIMESTAMPTZ,
    next_attempt_at TIMESTAMPTZ,
    last_error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        imo IS NOT NULL
        OR mmsi IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS
idx_vessel_enrichment_queue_status
ON public.vessel_enrichment_queue (
    queue_status,
    next_attempt_at
);

CREATE INDEX IF NOT EXISTS
idx_vessel_enrichment_queue_imo
ON public.vessel_enrichment_queue (imo);

COMMIT;

