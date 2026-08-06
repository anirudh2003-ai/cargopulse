INSERT INTO public.vessel_enrichment_queue (
    lookup_key,
    imo,
    mmsi,
    observed_vessel_name,
    queue_status,
    updated_at
)

SELECT DISTINCT ON (calls.imo)
    'imo:' || calls.imo::TEXT AS lookup_key,
    calls.imo,
    calls.mmsi,
    calls.vessel_name,
    'pending',
    NOW()

FROM public.validated_terminal_calls AS calls

LEFT JOIN public.vessel_registry AS registry
    ON registry.imo = calls.imo

WHERE calls.imo IS NOT NULL
  AND registry.imo IS NULL

ORDER BY
    calls.imo,
    calls.arrival_time DESC

ON CONFLICT (lookup_key)
DO UPDATE SET
    mmsi = EXCLUDED.mmsi,
    observed_vessel_name =
        EXCLUDED.observed_vessel_name,

    queue_status = CASE
        WHEN vessel_enrichment_queue.queue_status
             = 'processing'
        THEN 'processing'
        ELSE 'pending'
    END,

    next_attempt_at = NULL,
    last_error = NULL,
    updated_at = NOW();
